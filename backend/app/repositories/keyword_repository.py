"""
repositories/keyword_repository.py
=====================================
Abstract base class for keyword search (BM25) repository.

PURPOSE:
    Defines the contract for BM25 keyword search operations.
    ElasticsearchRepository implements this interface.

SOLID: Dependency Inversion — services depend on this abstraction.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.document import DocumentChunk, RetrievedChunk


class KeywordRepository(ABC):
    """Abstract repository for BM25 keyword search operations."""

    @abstractmethod
    async def index_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Bulk-index document chunks into the keyword search store."""
        ...

    @abstractmethod
    async def search(self, query: str, top_k: int, category_filter: Optional[str] = None) -> List[RetrievedChunk]:
        """Perform BM25 keyword search."""
        ...

    @abstractmethod
    async def delete_by_document_id(self, document_id: str) -> None:
        """Delete all chunks belonging to a document."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the keyword store is reachable and healthy."""
        ...
