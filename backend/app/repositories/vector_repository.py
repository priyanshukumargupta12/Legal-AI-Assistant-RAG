"""
repositories/vector_repository.py
====================================
Abstract base class for vector store repository.

PURPOSE:
    Defines the contract for all vector store operations.
    QdrantRepository implements this interface.
    Enables easy testing via mock implementations.

SOLID: Dependency Inversion — services depend on this abstraction.
       Liskov Substitution — any VectorRepository impl can replace Qdrant.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.document import DocumentChunk, RetrievedChunk


class VectorRepository(ABC):
    """Abstract repository for dense vector storage and retrieval."""

    @abstractmethod
    async def upsert_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        """Upsert chunk vectors with metadata into the vector store."""
        ...

    @abstractmethod
    async def search(self, query_vector: List[float], top_k: int, category_filter: Optional[str] = None) -> List[RetrievedChunk]:
        """Perform approximate nearest neighbor search."""
        ...

    @abstractmethod
    async def delete_by_document_id(self, document_id: str) -> None:
        """Delete all chunks belonging to a document."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the vector store is reachable and healthy."""
        ...
