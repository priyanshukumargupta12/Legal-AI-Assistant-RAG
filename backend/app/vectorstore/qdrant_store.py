"""
vectorstore/qdrant_store.py
============================
Qdrant vector store implementation of VectorRepository.

PURPOSE:
    Implements VectorRepository using the qdrant-client library.
    Manages collection creation, vector upsert, and similarity search.

MODES:
    memory → QdrantClient("":memory:"") — no installation needed
    local  → QdrantClient(url=QDRANT_URL) — local Qdrant server
    cloud  → QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

SOLID: Liskov Substitution — fully replaces VectorRepository contract.
       Dependency Inversion — imported only in infrastructure, not domain.
"""

from __future__ import annotations

from typing import List, Optional

from qdrant_client import QdrantClient

from app.core.config import Settings
from app.models.document import DocumentChunk, RetrievedChunk
from app.repositories.vector_repository import VectorRepository
from app.vectorstore.qdrant_service import QdrantService
from app.vectorstore.collection_manager import CollectionManager


class QdrantRepository(VectorRepository):
    """
    Qdrant implementation of VectorRepository.
    Integrates QdrantClient with core application requirements.
    """

    def __init__(self, client: QdrantClient, settings: Settings) -> None:
        """
        Initialize the repository.

        Args:
            client: Instantiated QdrantClient.
            settings: Loaded configuration settings.
        """
        self.client = client
        self.settings = settings
        self.service = QdrantService(client, settings)

        # Automatically manage collection on initialization if configured
        self._create_collection_if_not_exists()

    def _create_collection_if_not_exists(self) -> None:
        """
        Create collection in Qdrant automatically on initialization.
        """
        CollectionManager.create_collection_if_not_exists(
            client=self.client,
            collection_name=self.settings.qdrant_collection_name,
            dimension=384,  # bge-small-en-v1.5
        )

    async def upsert_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        """
        Upsert a batch of chunks and embeddings.
        """
        await self.service.upsert_chunks(chunks, embeddings)

    async def search(
        self,
        query_vector: List[float],
        top_k: int,
        category_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Search approximate nearest neighbors.
        """
        return await self.service.search(query_vector, top_k, category_filter)

    async def delete_by_document_id(self, document_id: str) -> None:
        """
        Delete document vectors.
        """
        await self.service.delete_by_document_id(document_id)

    async def health_check(self) -> bool:
        """
        Perform health check.
        """
        return await self.service.health_check()

