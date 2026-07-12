"""
app/vectorstore/__init__.py
==========================
Qdrant Vector Database Module — public interface.

PURPOSE:
    Exposes all vector store integration components and factories.
"""

from __future__ import annotations

from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.qdrant_service import QdrantService
from app.vectorstore.collection_manager import CollectionManager
from app.vectorstore.payload_builder import PayloadBuilder
from app.vectorstore.qdrant_store import QdrantRepository

__all__ = [
    "get_qdrant_client",
    "QdrantService",
    "CollectionManager",
    "PayloadBuilder",
    "QdrantRepository",
]
