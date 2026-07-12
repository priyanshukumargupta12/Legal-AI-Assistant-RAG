from __future__ import annotations

from typing import List
import numpy as np
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.exceptions import EmbeddingModelLoadError, EmbeddingError
from app.embeddings.embedding_logger import embedding_log


class BGEEmbedder:
    """
    Google Gemini Cloud Embeddings wrapper using the new google-genai SDK.
    Uses gemini-embedding-001 which outputs 3072 dimensions, sliced to 384
    to match the existing Qdrant collection schema.
    """

    MODEL_NAME = "gemini-embedding-001"
    TARGET_DIM = 384

    _instance: BGEEmbedder | None = None

    def __new__(cls, model_name: str = "gemini-embedding-001", cache_dir: str | None = None) -> BGEEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "gemini-embedding-001", cache_dir: str | None = None) -> None:
        if self._initialized:
            return

        self.settings = get_settings()

        embedding_log.info(
            "Initializing Cloud BGEEmbedder (Gemini API) | model={model}",
            model=self.MODEL_NAME,
        )

        try:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
            # Warm-up / verify connection
            self._client.models.embed_content(
                model=self.MODEL_NAME,
                contents="test",
            )
            self._initialized = True
            embedding_log.info(
                "Cloud embedding client configured successfully | model={model}",
                model=self.MODEL_NAME,
            )
        except Exception as exc:
            embedding_log.error(
                "Failed to configure Google GenAI client | error={error}", error=str(exc)
            )
            raise EmbeddingModelLoadError(self.MODEL_NAME, str(exc)) from exc

    # ── helpers ────────────────────────────────────────────────────────────────

    def _slice_and_normalize(self, vec: list[float]) -> list[float]:
        arr = np.array(vec[: self.TARGET_DIM], dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()

    # ── public API ─────────────────────────────────────────────────────────────

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Encode document chunks and return 384-dim L2-normalised vectors."""
        if not texts:
            return []

        try:
            response = self._client.models.embed_content(
                model=self.MODEL_NAME,
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            return [self._slice_and_normalize(e.values) for e in response.embeddings]
        except Exception as exc:
            embedding_log.error(
                "Failed to embed documents via Cloud API | error={error}", error=str(exc)
            )
            raise EmbeddingError(
                "Failed to generate document embeddings.", batch_size=len(texts)
            ) from exc

    def embed_query(self, text: str) -> List[float]:
        """Encode a search query and return a 384-dim L2-normalised vector."""
        if not text:
            raise ValueError("Query text cannot be empty.")

        try:
            response = self._client.models.embed_content(
                model=self.MODEL_NAME,
                contents=text,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
            )
            return self._slice_and_normalize(response.embeddings[0].values)
        except Exception as exc:
            embedding_log.error(
                "Failed to embed query via Cloud API | error={error}", error=str(exc)
            )
            raise EmbeddingError(f"Failed to generate query embedding: {exc}") from exc
