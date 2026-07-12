"""
app/embeddings/__init__.py
==========================
Dense Embedding Module — public interface.

PURPOSE:
    Exposes stable public objects of the Embedding Module.
"""

from __future__ import annotations

from app.embeddings.embedder import BGEEmbedder
from app.embeddings.embedding_models import EmbeddingStatistics
from app.embeddings.embedding_repository import (
    EmbeddingRepository,
    FileSystemEmbeddingRepository,
)
from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.embedding_controller import router as embedding_router

__all__ = [
    "BGEEmbedder",
    "EmbeddingStatistics",
    "EmbeddingRepository",
    "FileSystemEmbeddingRepository",
    "EmbeddingService",
    "embedding_router",
]
