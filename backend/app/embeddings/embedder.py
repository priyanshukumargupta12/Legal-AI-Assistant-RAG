from __future__ import annotations

from typing import List
import numpy as np
import google.generativeai as genai

from app.core.config import get_settings
from app.core.exceptions import EmbeddingModelLoadError, EmbeddingError
from app.embeddings.embedding_logger import embedding_log

class BGEEmbedder:
    """
    Google Gemini Cloud Embeddings wrapper (dimension = 384).
    Uses models/embedding-001 (Gecko) sliced to 384 dimensions to guarantee universal regional availability.
    """

    _instance: BGEEmbedder | None = None

    def __new__(cls, model_name: str = "models/embedding-001", cache_dir: str | None = None) -> BGEEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "models/embedding-001", cache_dir: str | None = None) -> None:
        if self._initialized:
            return

        self.model_name = "models/embedding-001" # Universally available model
        self.settings = get_settings()
        
        embedding_log.info(
            "Initializing Cloud BGEEmbedder (Gemini API) | model={model}",
            model=self.model_name
        )

        try:
            genai.configure(api_key=self.settings.gemini_api_key)
            # Test connection and slicing / warm up
            res = genai.embed_content(
                model=self.model_name,
                content="test",
                task_type="retrieval_query"
            )
            self._initialized = True
            embedding_log.info("Cloud embedding client configured and verified successfully.")
        except Exception as exc:
            embedding_log.error("Failed to configure Google GenAI client | error={error}", error=str(exc))
            raise EmbeddingModelLoadError(self.model_name, str(exc)) from exc

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Encode document chunks using the Gemini API and slice to 384 dimensions.
        """
        if not texts:
            return []

        try:
            response = genai.embed_content(
                model=self.model_name,
                content=texts,
                task_type="retrieval_document"
            )
            raw_embeddings = response['embedding']
            
            # Slice 768 dim to 384 dim and L2-normalize to match existing Qdrant collection schema
            processed_embeddings = []
            for emb in raw_embeddings:
                sliced = emb[:384]
                arr = np.array(sliced)
                norm = np.linalg.norm(arr)
                if norm > 0:
                    arr = arr / norm
                processed_embeddings.append(arr.tolist())
                
            return processed_embeddings
        except Exception as exc:
            embedding_log.error("Failed to embed documents via Cloud API | error={error}", error=str(exc))
            raise EmbeddingError("Failed to generate document embeddings.", batch_size=len(texts)) from exc

    def embed_query(self, text: str) -> List[float]:
        """
        Encode search query using the Gemini API and slice to 384 dimensions.
        """
        if not text:
            raise ValueError("Query text cannot be empty.")

        try:
            response = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_query"
            )
            raw_emb = response['embedding']
            
            # Slice 768 dim to 384 dim and L2-normalize
            sliced = raw_emb[:384]
            arr = np.array(sliced)
            norm = np.linalg.norm(arr)
            if norm > 0:
                arr = arr / norm
                
            return arr.tolist()
        except Exception as exc:
            embedding_log.error("Failed to embed query via Cloud API | error={error}", error=str(exc))
            raise EmbeddingError(f"Failed to generate query embedding: {exc}") from exc
