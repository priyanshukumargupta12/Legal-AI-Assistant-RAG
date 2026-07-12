"""
app/api/routes/elasticsearch.py
===============================
FastAPI routes for Elasticsearch BM25 indexing orchestration.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from app.api.dependencies.services import get_elasticsearch_service
from app.api.responses.standard_response import StandardResponse
from app.elasticsearch.elastic_service import ElasticsearchService
from app.elasticsearch.elastic_logger import elastic_log
from app.core.config import Settings, get_settings

# The user requested: POST /api/v1/index
router = APIRouter(prefix="/index", tags=["Elasticsearch"])


@router.post(
    "",
    response_model=StandardResponse,
    summary="Index all document chunks in Elasticsearch for BM25 keyword search",
)
async def index_all_chunks(
    service: Annotated[ElasticsearchService, Depends(get_elasticsearch_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Optional[int] = Query(default=None, description="Optional limit on count of documents indexed (for quick testing)"),
) -> StandardResponse:
    """
    Scans the metadata/chunks directory, indexes all document chunks into Elasticsearch,
    and returns indexing statistics.
    """
    start_time = time.perf_counter()

    chunks_dir = Path(settings.metadata_path) / "chunks"
    if not chunks_dir.exists():
        return StandardResponse.success(
            data={"indexed_count": 0, "details": []},
            message="No chunk files found. Run chunking first."
        )

    # Automatically create Elasticsearch index with legal_analyzer if it does not exist
    service.ensure_index()

    # Find all chunks JSON files
    chunk_files = list(chunks_dir.glob("*_chunks.json"))
    if limit is not None:
        chunk_files = chunk_files[:limit]

    indexed_docs = []
    failed_docs = []
    total_indexed = 0

    for file_path in chunk_files:
        doc_id = file_path.name.replace("_chunks.json", "")
        try:
            stats = await service.index_document(document_id=doc_id)
            total_indexed += stats["indexed"]
            indexed_docs.append({
                "document_id": doc_id,
                "chunks_count": stats["total"],
                "indexed_count": stats["indexed"]
            })
        except Exception as exc:
            elastic_log.error("Failed to index document chunks in ES | id={id} | error={err}", id=doc_id, err=str(exc))
            failed_docs.append({
                "document_id": doc_id,
                "error": str(exc)
            })

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    data = {
        "indexed_count": len(indexed_docs),
        "failed_count": len(failed_docs),
        "total_indexed_chunks": total_indexed,
        "indexed_details": indexed_docs,
        "failed_details": failed_docs,
        "elapsed_time_ms": elapsed_ms
    }

    return StandardResponse.success(
        data=data,
        message=f"Elasticsearch indexing complete. Indexed {total_indexed} chunks successfully."
    )
