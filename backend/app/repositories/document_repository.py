"""
repositories/document_repository.py
======================================
Abstract base class for document metadata repository.

PURPOSE:
    Manages persistence of DocumentMetadata records (stored in JSON/CSV).

SOLID: Dependency Inversion — services depend on this abstraction.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.document import DocumentMetadata


class DocumentRepository(ABC):
    """Abstract repository for document metadata persistence."""

    @abstractmethod
    async def save(self, metadata: DocumentMetadata) -> None:
        """Persist a DocumentMetadata record."""
        ...

    @abstractmethod
    async def find_by_id(self, document_id: str) -> Optional[DocumentMetadata]:
        """Find a document by its UUID."""
        ...

    @abstractmethod
    async def find_by_hash(self, md5_hash: str) -> Optional[DocumentMetadata]:
        """Find a document by MD5 hash (for duplicate detection)."""
        ...

    @abstractmethod
    async def find_all(self) -> List[DocumentMetadata]:
        """Return all stored document metadata records."""
        ...
