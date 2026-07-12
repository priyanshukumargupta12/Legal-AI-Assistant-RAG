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
    Uses models/text-embedding-004 in the cloud to bypass local memory limits.
    """

    _instance: BGEEmbedder | None = None

    def __new__(cls, model_name: str = "models/text-embedding-004", cache_dir: str | None = None) -> BGEEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "models/text-embedding-004", cache_dir: str | None = None) -> None:
        if self._initialized:
            return

        self.model_name = "models/text-embedding-004" # Force cloud model
        self.settings = get_settings()
        
        embedding_log.info(
            "Initializing Cloud BGEEmbedder (Gemini API) | model={model}",
            model=self.model_name
        )

        try:
            genai.configure(api_key=self.settings.gemini_api_key)
            # Test connection / warm up
            genai.embed_content(
                model=self.model_name,
                content="test",
                task_type="retrieval_query",
                output_dimensionality=384
            )
            self._initialized = True
            embedding_log.info("Cloud embedding client configured and verified successfully.")
        except Exception as exc:
            embedding_log.error("Failed to configure Google GenAI client | error={error}", error=str(exc))
            raise EmbeddingModelLoadError(self.model_name, str(exc)) from exc

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Encode document chunks using the Gemini API.
        """
        if not texts:
            return []

        try:
            response = genai.embed_content(
                model=self.model_name,
                content=texts,
                task_type="retrieval_document",
                output_dimensionality=384
            )
            return response['embedding']
        except Exception as exc:
            embedding_log.error("Failed to embed documents via Cloud API | error={error}", error=str(exc))
            raise EmbeddingError("Failed to generate document embeddings.", batch_size=len(texts)) from exc

    def embed_query(self, text: str) -> List[float]:
        """
        Encode search query using the Gemini API.
        """
        if not text:
            raise ValueError("Query text cannot be empty.")

        try:
            response = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_query",
                output_dimensionality=384
            )
            return response['embedding']
        except Exception as exc:
            embedding_log.error("Failed to embed query via Cloud API | error={error}", error=str(exc))
            raise EmbeddingError(f"Failed to generate query embedding: {exc}") from exc
