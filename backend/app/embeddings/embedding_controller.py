"""
app/embeddings/embedding_controller.py
======================================
HTTP controller for the Dense Embedding Module.

DEPRECATION WARNING:
    This controller is legacy dead code.
    Active API routes for embedding generation are aggregated in:
        app/api/routes/embeddings.py
    Refer to that module for production endpoints.

PURPOSE:
    Exposes FastAPI endpoints to trigger vector embedding generation and Qdrant index
    insertion for document chunks.

ROUTES:
    POST /embeddings/embed/{document_id}
        Generates and indexes vector representations for a single document.
    POST /embeddings/embed/batch
        Processes a list of document IDs sequentially.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.config import get_settings
from app.core.exceptions import LegalAssistantError
from app.embeddings.embedding_logger import embedding_log
from app.embeddings.embedding_repository import FileSystemEmbeddingRepository
from app.embeddings.embedding_schemas import (
    EmbeddingRequestSchema,
    EmbeddingResponseSchema,
    EmbeddingStatisticsSchema,
)
from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.embedder import BGEEmbedder
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.qdrant_store import QdrantRepository

router = APIRouter(
    prefix="/embeddings",
    tags=["Dense Embeddings"],
)


# ─── Dependency Injection Factory ─────────────────────────────────────────────

def get_embedding_service() -> EmbeddingService:
    """
    Dependency factory to assemble and retrieve the EmbeddingService instance.
    """
    settings = get_settings()

    # Load BGE singleton embedder
    embedder = BGEEmbedder(
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_cache_dir,
    )

    # Initialize repository
    repository = FileSystemEmbeddingRepository(
        metadata_dir=Path(settings.metadata_path)
    )

    # Wire Qdrant repository
    qdrant_client = get_qdrant_client(settings)
    vector_repository = QdrantRepository(
        client=qdrant_client,
        settings=settings,
    )

    return EmbeddingService(
        embedder=embedder,
        repository=repository,
        vector_repository=vector_repository,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post(
    "/embed/{document_id}",
    response_model=EmbeddingResponseSchema,
    summary="Generate embeddings for document chunks and index in Qdrant",
    description="Loads a document's chunks, runs BGE model embedding, and upserts them to Qdrant.",
)
async def embed_document(
    document_id: str,
    service: EmbeddingService = Depends(get_embedding_service),
) -> EmbeddingResponseSchema:
    """
    Trigger embedding generation and database ingestion for a single document.
    """
    try:
        stats = await service.embed_document(
            document_id=document_id,
            batch_size=get_settings().embedding_batch_size,
        )

        stats_schema = EmbeddingStatisticsSchema(
            total_chunks=stats.total_chunks,
            embedded_chunks=stats.embedded_chunks,
            failed_chunks=stats.failed_chunks,
            average_embedding_time=stats.average_embedding_time,
            embedding_dimension=stats.embedding_dimension,
            processed_at=stats.processed_at,
        )

        return EmbeddingResponseSchema(
            status="success",
            statistics=stats_schema,
            message=f"Successfully embedded document '{document_id}'.",
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Parsed chunks for document '{document_id}' not found. Run chunker first: {exc}",
        ) from exc
    except LegalAssistantError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc
    except Exception as exc:
        embedding_log.exception("Unexpected error in embed_document route")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected embedding error: {exc}",
        ) from exc


@router.post(
    "/embed/batch",
    response_model=EmbeddingResponseSchema,
    summary="Batch generate embeddings and index chunks",
    description="Runs the embedding pipeline sequentially across a list of document IDs.",
)
async def embed_documents_batch(
    request: EmbeddingRequestSchema,
    service: EmbeddingService = Depends(get_embedding_service),
) -> EmbeddingResponseSchema:
    """
    Batch index chunks from a list of documents.
    """
    document_ids = request.document_ids
    if not document_ids:
        raise HTTPException(
            status_code=400,
            detail="Document ID list must not be empty.",
        )

    import time
    from datetime import datetime, timezone
    from app.embeddings.embedding_models import EmbeddingStatistics

    total_chunks = 0
    embedded_chunks = 0
    failed_chunks = 0
    run_start = time.perf_counter()

    batch_size = get_settings().embedding_batch_size

    for doc_id in document_ids:
        try:
            stats = await service.embed_document(
                document_id=doc_id,
                batch_size=batch_size,
            )
            total_chunks += stats.total_chunks
            embedded_chunks += stats.embedded_chunks
            failed_chunks += stats.failed_chunks
        except Exception as exc:
            embedding_log.error(
                "Document failed in batch embedding | id={doc_id} | error={error}",
                doc_id=doc_id,
                error=str(exc),
            )
            # Count remaining chunks as failed if we could know them, otherwise record failure
            failed_chunks += 1

    total_elapsed = time.perf_counter() - run_start
    avg_time = (total_elapsed / total_chunks) if total_chunks > 0 else 0.0

    aggregated_stats = EmbeddingStatistics(
        total_chunks=total_chunks,
        embedded_chunks=embedded_chunks,
        failed_chunks=failed_chunks,
        average_embedding_time=avg_time,
        embedding_dimension=384,
        processed_at=datetime.now(timezone.utc),
    )

    # Persist aggregated stats
    try:
        service.repository.save_embedding_statistics(aggregated_stats)
    except Exception as exc:
        embedding_log.error(
            "Failed to save aggregated batch stats | error={error}",
            error=str(exc),
        )

    stats_schema = EmbeddingStatisticsSchema(
        total_chunks=aggregated_stats.total_chunks,
        embedded_chunks=aggregated_stats.embedded_chunks,
        failed_chunks=aggregated_stats.failed_chunks,
        average_embedding_time=aggregated_stats.average_embedding_time,
        embedding_dimension=aggregated_stats.embedding_dimension,
        processed_at=aggregated_stats.processed_at,
    )

    return EmbeddingResponseSchema(
        status="success",
        statistics=stats_schema,
        message=f"Batch embedding run complete. Processed {len(document_ids)} documents.",
    )
