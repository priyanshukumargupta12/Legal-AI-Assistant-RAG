"""
app/api/routes/chunking.py
==========================
FastAPI routes for document chunking orchestration.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from app.api.dependencies.services import get_chunking_service
from app.api.responses.standard_response import StandardResponse
from app.chunking.chunk_service import ChunkingService
from app.chunking.chunk_logger import chunk_log
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/chunk", tags=["Intelligent Chunking"])


@router.post(
    "",
    response_model=StandardResponse,
    summary="Generate chunks for all parsed documents",
)
async def generate_chunks(
    service: Annotated[ChunkingService, Depends(get_chunking_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Optional[int] = Query(default=None, description="Optional limit on count of documents chunked (for quick testing)"),
) -> StandardResponse:
    """
    Scans the metadata/parsed directory, runs the intelligent RecursiveCharacterTextSplitter
    on each page's extracted text, and generates standardized chunk JSON files.
    """
    start_time = time.perf_counter()

    parsed_dir = Path(settings.metadata_path) / "parsed"
    if not parsed_dir.exists():
        return StandardResponse.success(
            data={"chunks_generated": 0, "details": []},
            message="No parsed documents found. Run parse first."
        )

    # Find all parsed document JSON files
    parsed_files = list(parsed_dir.glob("*.json"))
    if limit is not None:
        parsed_files = parsed_files[:limit]

    chunked_docs = []
    failed_docs = []
    total_chunks = 0

    for file_path in parsed_files:
        doc_id = file_path.stem
        try:
            chunks, stats = service.chunk_by_document_id(
                document_id=doc_id,
                parsed_dir=parsed_dir,
            )
            total_chunks += len(chunks)
            chunked_docs.append({
                "document_id": doc_id,
                "document_name": stats.document_name,
                "chunks_count": stats.total_chunks,
            })
        except Exception as exc:
            chunk_log.error("Failed to chunk document | id={id} | error={err}", id=doc_id, err=str(exc))
            failed_docs.append({
                "document_id": doc_id,
                "error": str(exc),
            })

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    data = {
        "chunked_count": len(chunked_docs),
        "failed_count": len(failed_docs),
        "total_chunks": total_chunks,
        "chunked_details": chunked_docs,
        "failed_details": failed_docs,
        "elapsed_time_ms": elapsed_ms,
    }

    return StandardResponse.success(
        data=data,
        message=f"Document chunking complete. Generated {total_chunks} chunks successfully."
    )
