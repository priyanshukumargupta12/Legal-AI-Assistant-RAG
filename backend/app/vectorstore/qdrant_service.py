"""
app/vectorstore/qdrant_service.py
================================
Qdrant interaction service.

PURPOSE:
    Provides the concrete implementation of vector store operations.
    Handles upserts, searches with category filters, deletion of document chunks,
    and connection health checking.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct, NamedVector

from app.core.config import Settings
from app.core.exceptions import VectorStoreError
from app.models.document import DocumentChunk, RetrievedChunk
from app.vectorstore.payload_builder import PayloadBuilder
from app.vectorstore.vector_logger import vector_log


class QdrantService:
    """
    Service layer interacting with the QdrantClient.
    """

    def __init__(self, client: QdrantClient, settings: Settings) -> None:
        """
        Initialize with client and configuration settings.
        """
        self.client = client
        self.settings = settings
        self.collection_name = settings.qdrant_collection_name

    async def upsert_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        """
        Upsert a list of document chunks and their dense embeddings into Qdrant.

        Args:
            chunks: List of DocumentChunk models.
            embeddings: Parallel list of dense float32 vectors.
        """
        if not chunks or not embeddings:
            return

        if len(chunks) != len(embeddings):
            raise ValueError("Size of chunks and embeddings lists must match.")

        points = []
        for chunk, emb in zip(chunks, embeddings):
            # Generate a deterministic UUID from the unique chunk_id string
            # to support idempotent upserts and avoid duplicates.
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            payload = PayloadBuilder.build_payload(chunk)

            points.append(
                PointStruct(
                    id=point_id,
                    vector={"dense": emb},
                    payload=payload,
                )
            )

        try:
            vector_log.info(
                "Upserting vectors into Qdrant | collection={col} | count={count}",
                col=self.collection_name,
                count=len(points),
            )
            # Perform upsert operation
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,  # Block until indexed
            )
        except Exception as exc:
            vector_log.error(
                "Qdrant upsert failed | collection={col} | error={error}",
                col=self.collection_name,
                error=str(exc),
            )
            raise VectorStoreError(
                message=f"Failed to upsert chunks to Qdrant collection '{self.collection_name}': {exc}",
                operation="upsert",
            ) from exc

    async def search(
        self,
        query_vector: List[float],
        top_k: int,
        category_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Perform approximate nearest neighbor search.

        Args:
            query_vector: Dense query vector.
            top_k: Number of results to return.
            category_filter: Optional document category to pre-filter results.

        Returns:
            List of RetrievedChunk domain entities.
        """
        qdrant_filter = None
        if category_filter:
            vector_log.info(
                "Applying category pre-filter | filter={filter}",
                filter=category_filter,
            )
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category_filter),
                    )
                ]
            )

        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using="dense",
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True,
                score_threshold=self.settings.vector_score_threshold,
            )
            results = response.points
        except Exception as exc:
            vector_log.error(
                "Qdrant search failed | collection={col} | error={error}",
                col=self.collection_name,
                error=str(exc),
            )
            raise VectorStoreError(
                message=f"Qdrant search failed: {exc}",
                operation="search",
            ) from exc

        retrieved_chunks = []
        for rank, res in enumerate(results, start=1):
            payload = res.payload or {}
            
            page_num = payload.get("page_number") or payload.get("page") or payload.get("metadata", {}).get("page_number")
            if page_num is None:
                raise ValueError(f"page_number is missing in Qdrant payload for chunk {payload.get('chunk_id')}")
            chunk_idx = payload.get("chunk_index") or 0

            chunk = RetrievedChunk(
                chunk_id=payload.get("chunk_id", str(res.id)),
                document_id=payload.get("document_id", ""),
                document_name=payload.get("document_name", ""),
                category=payload.get("category", ""),
                page_number=int(page_num),
                chunk_index=int(chunk_idx),
                text=payload.get("chunk_text", ""),
                score=float(res.score),
                rank=rank,
                source="vector",
            )
            retrieved_chunks.append(chunk)

        return retrieved_chunks

    async def delete_by_document_id(self, document_id: str) -> None:
        """
        Delete all vectors belonging to a specific document ID.

        Args:
            document_id: UUID of the document.
        """
        vector_log.warning(
            "Deleting document vectors from Qdrant | collection={col} | document_id={doc_id}",
            col=self.collection_name,
            doc_id=document_id,
        )

        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                ),
                wait=True,
            )
        except Exception as exc:
            vector_log.error(
                "Failed to delete document from Qdrant | document_id={doc_id} | error={error}",
                doc_id=document_id,
                error=str(exc),
            )
            raise VectorStoreError(
                message=f"Failed to delete vectors for document '{document_id}': {exc}",
                operation="delete",
            ) from exc

    async def health_check(self) -> bool:
        """
        Check connectivity and health of the Qdrant service.
        """
        try:
            # Check cluster status by listing collections
            self.client.get_collections()
            return True
        except Exception as exc:
            vector_log.error("Qdrant health check failed | error={error}", error=str(exc))
            return False
