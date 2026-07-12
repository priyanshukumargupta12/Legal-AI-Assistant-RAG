"""
embeddings/embedder.py
=======================
BGE embedding model wrapper using sentence-transformers.

PURPOSE:
    Loads BAAI/bge-small-en-v1.5 once at startup (singleton pattern).
    Encodes document chunks in batches and query text with instruction prefix.
    Returns L2-normalized 384-dimensional float32 vectors.

WHY BGE-small:
    - Top MTEB retrieval score for <50M parameter models
    - 384 dimensions: fast Qdrant search, minimal memory
    - Instruction-tuned: separate corpus vs query encoding
    - MIT license, runs on CPU without GPU

SOLID: Single Responsibility — embedding generation only.
       Dependency Inversion — implements abstract Embedder interface.
"""

from __future__ import annotations

from typing import List
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.core.exceptions import EmbeddingModelLoadError, EmbeddingError
from app.embeddings.embedding_logger import embedding_log

# ─── BGE Query Instruction Prefix ─────────────────────────────────────────────
# Required by BAAI/bge models to align short search queries with long document texts.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class BGEEmbedder:
    """
    BAAI/bge-small-en-v1.5 embedding model wrapper.
    Implements a thread-safe singleton pattern to ensure the model weights
    are loaded exactly once at startup.
    """

    _instance: BGEEmbedder | None = None

    def __new__(cls, model_name: str = "BAAI/bge-small-en-v1.5", cache_dir: str | None = None) -> BGEEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", cache_dir: str | None = None) -> None:
        if self._initialized:
            return

        self.model_name = model_name
        self.cache_dir = cache_dir
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model: SentenceTransformer | None = None

        embedding_log.info(
            "Initializing BGEEmbedder | model={model} | cache={cache} | device={device}",
            model=self.model_name,
            cache=self.cache_dir or "default",
            device=self.device,
        )

        self._model = self._load_model()
        self._initialized = True
        embedding_log.info("Embedding model loaded successfully.")

    def _load_model(self) -> SentenceTransformer:
        """
        Load the SentenceTransformer model weights.
        """
        try:
            return SentenceTransformer(
                model_name_or_path=self.model_name,
                cache_folder=self.cache_dir,
                device=self.device,
            )
        except Exception as exc:
            embedding_log.error(
                "Model loading failed | model={model} | error={error}",
                model=self.model_name,
                error=str(exc),
            )
            raise EmbeddingModelLoadError(self.model_name, str(exc)) from exc

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of text segments (chunks) into dense embeddings.
        No query instruction prefix is prepended to documents.

        Args:
            texts: List of document chunk strings.

        Returns:
            List of 384-dimensional float lists.
        """
        if not texts:
            return []

        try:
            embeddings_np = self._encode_batch(texts, add_instruction=False)
            return embeddings_np.tolist()
        except Exception as exc:
            embedding_log.error("Failed to embed documents | error={error}", error=str(exc))
            raise EmbeddingError("Failed to generate document embeddings.", batch_size=len(texts)) from exc

    def embed_query(self, text: str) -> List[float]:
        """
        Encode a single search query with the required instruction prefix.

        Args:
            text: Search query string.

        Returns:
            384-dimensional float vector.
        """
        if not text:
            raise ValueError("Query text cannot be empty.")

        try:
            # Wrap query in a list, prepend instruction, encode, and get the single vector
            query_with_prefix = f"{QUERY_INSTRUCTION}{text}"
            embeddings_np = self._encode_batch([query_with_prefix], add_instruction=True)
            return embeddings_np[0].tolist()
        except Exception as exc:
            embedding_log.error("Failed to embed query | error={error}", error=str(exc))
            raise EmbeddingError(f"Failed to generate query embedding: {exc}") from exc

    def _encode_batch(self, texts: List[str], add_instruction: bool) -> np.ndarray:
        """
        Execute raw model encoding. Ensures L2 normalization is applied.
        """
        if self._model is None:
            raise EmbeddingError("Embedding model is not initialized.")

        # normalize_embeddings=True ensures vectors are L2-normalized,
        # which makes cosine similarity equivalent to a simple dot product.
        return self._model.encode(
            sentences=texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            device=self.device,
        )

