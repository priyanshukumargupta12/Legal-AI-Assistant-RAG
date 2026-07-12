"""
app/api/routes/embeddings.py
=============================
FastAPI routes for dense embedding generation and indexing in Qdrant.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from app.api.dependencies.services import get_embedding_service
from app.api.responses.standard_response import StandardResponse
from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.embedding_logger import embedding_log
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/embed", tags=["Dense Embeddings"])


@router.post(
    "",
    response_model=StandardResponse,
    summary="Generate embeddings for all document chunks",
)
async def generate_embeddings(
    service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Optional[int] = Query(default=None, description="Optional limit on count of documents embedded (for quick testing)"),
) -> StandardResponse:
    """
    Scans the metadata/chunks directory, generates dense vector embeddings for
    all chunks, and uploads the payload-bound vectors to Qdrant.
    """
    start_time = time.perf_counter()

    chunks_dir = Path(settings.metadata_path) / "chunks"
    if not chunks_dir.exists():
        return StandardResponse.success(
            data={"embedded_count": 0, "details": []},
            message="No chunk files found. Run chunking first."
        )

    # Find all chunks JSON files
    chunk_files = list(chunks_dir.glob("*_chunks.json"))
    if limit is not None:
        chunk_files = chunk_files[:limit]

    embedded_docs = []
    failed_docs = []
    total_embedded = 0

    for file_path in chunk_files:
        # Get document ID by removing '_chunks' suffix from the filename stem
        doc_id = file_path.name.replace("_chunks.json", "")
        try:
            stats = await service.embed_document(document_id=doc_id, batch_size=32)
            total_embedded += stats.embedded_chunks
            embedded_docs.append({
                "document_id": doc_id,
                "chunks_count": stats.total_chunks,
                "embedded_count": stats.embedded_chunks,
            })
        except Exception as exc:
            embedding_log.error("Failed to generate embeddings | id={id} | error={err}", id=doc_id, err=str(exc))
            failed_docs.append({
                "document_id": doc_id,
                "error": str(exc),
            })

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    data = {
        "embedded_count": len(embedded_docs),
        "failed_count": len(failed_docs),
        "total_embedded_chunks": total_embedded,
        "embedded_details": embedded_docs,
        "failed_details": failed_docs,
        "elapsed_time_ms": elapsed_ms,
    }

    return StandardResponse.success(
        data=data,
        message=f"Dense embedding generation and Qdrant indexing complete. Upserted {total_embedded} vectors successfully."
    )
