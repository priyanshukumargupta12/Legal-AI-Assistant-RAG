"""
app/vectorstore/collection_manager.py
=====================================
Qdrant collection management.

PURPOSE:
    Handles automatic detection and creation of the vector database collection.
    Configures vector dimensions and distance metrics (Cosine similarity).
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from app.core.exceptions import VectorStoreError
from app.vectorstore.vector_logger import vector_log


class CollectionManager:
    """
    Manages collection creation, status verification, and deletion.
    """

    @staticmethod
    def collection_exists(client: QdrantClient, collection_name: str) -> bool:
        """
        Check if a collection exists in Qdrant.
        """
        try:
            client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

    @classmethod
    def create_collection_if_not_exists(
        cls,
        client: QdrantClient,
        collection_name: str,
        dimension: int = 384,
    ) -> None:
        """
        Create a new Qdrant collection if it does not already exist.

        Configured with COSINE distance metric and the specified dimension.
        """
        if cls.collection_exists(client, collection_name):
            vector_log.info(
                "Qdrant collection already exists | collection={name}",
                name=collection_name,
            )
            return

        vector_log.info(
            "Creating Qdrant collection | collection={name} | dimension={dim} | metric=Cosine",
            name=collection_name,
            dim=dimension,
        )

        try:
            client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=dimension,
                        distance=Distance.COSINE,
                    )
                },
            )
            vector_log.info(
                "Successfully created Qdrant collection | collection={name}",
                name=collection_name,
            )
        except Exception as exc:
            exc_str = str(exc).lower()
            if "already exists" in exc_str or "409" in exc_str:
                vector_log.info(
                    "Qdrant collection already exists (ignored conflict during creation) | collection={name}",
                    name=collection_name,
                )
                return
            vector_log.error(
                "Failed to create Qdrant collection | collection={name} | error={error}",
                name=collection_name,
                error=str(exc),
            )
            raise VectorStoreError(
                message=f"Failed to create Qdrant collection '{collection_name}': {exc}",
                operation="create_collection",
            ) from exc

    @classmethod
    def recreate_collection(
        cls,
        client: QdrantClient,
        collection_name: str,
        dimension: int = 384,
    ) -> None:
        """
        Force delete and recreate a Qdrant collection.
        """
        vector_log.warning(
            "Recreating Qdrant collection | collection={name}",
            name=collection_name,
        )
        try:
            if cls.collection_exists(client, collection_name):
                client.delete_collection(collection_name=collection_name)
            cls.create_collection_if_not_exists(client, collection_name, dimension)
        except Exception as exc:
            vector_log.error(
                "Failed to recreate Qdrant collection | collection={name} | error={error}",
                name=collection_name,
                error=str(exc),
            )
            raise VectorStoreError(
                message=f"Failed to recreate Qdrant collection '{collection_name}': {exc}",
                operation="recreate_collection",
            ) from exc
