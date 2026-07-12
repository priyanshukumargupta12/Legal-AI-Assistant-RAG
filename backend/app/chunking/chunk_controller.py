"""
app/chunking/chunk_controller.py
=================================
HTTP controller for the Intelligent Chunking Module.

DEPRECATION WARNING:
    This controller is legacy dead code.
    Active API routes for chunking are aggregated in:
        app/api/routes/chunking.py
    Refer to that module for production endpoints.

PURPOSE:
    Exposes FastAPI routes that trigger chunking on a parsed document
    and retrieve previously generated chunk output. Acts as the HTTP
    adapter layer between external callers and ChunkingService.

ROUTES:
    POST /chunker/chunk/{document_id}
        Triggers chunking for a single parsed document. Loads the parser
        output JSON from metadata/parsed/, splits text into chunks, writes
        chunks.json, and returns a ChunkingResponseSchema.

    GET  /chunker/output/{document_id}
        Returns the previously generated chunks for a document by reading
        the stored chunks.json file.

    POST /chunker/chunk/batch
        Triggers sequential chunking for a list of document IDs.
        Returns GlobalChunkStatsSchema.

DESIGN:
    - Thin controller: No business logic here. All logic lives in ChunkingService.
    - Dependency injection via FastAPI's Depends() mechanism.
    - Errors from the service layer are mapped to HTTP status codes.
    - All routes are async (FastAPI best practice for I/O-bound operations).

NOTE:
    This controller follows the existing project pattern. No new API routes
    have been added beyond what is required by the specification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException

from app.chunking.chunk_models import GlobalChunkStats
from app.chunking.chunk_repository import FileSystemChunkRepository
from app.chunking.chunk_schemas import (
    ChunkingResponseSchema,
    ChunkSchema,
    ChunkStatisticsSchema,
    GlobalChunkStatsSchema,
)
from app.chunking.chunk_service import ChunkingService
from app.core.config import get_settings
from app.core.exceptions import ChunkingError

router = APIRouter(
    prefix="/chunker",
    tags=["Intelligent Chunking"],
)


# ─── Dependency Injection Factory ─────────────────────────────────────────────

def get_chunking_service() -> ChunkingService:
    """
    FastAPI dependency factory for ChunkingService.

    Reads path configuration from Settings, constructs the repository,
    and returns a fully-wired ChunkingService instance. Called once per request.

    Returns:
        Configured ChunkingService instance.
    """
    settings = get_settings()
    output_dir = Path(settings.metadata_path) / "chunks"
    repository = FileSystemChunkRepository()

    return ChunkingService(
        repository=repository,
        output_dir=output_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post(
    "/chunk/{document_id}",
    response_model=ChunkingResponseSchema,
    summary="Split a parsed document into semantic chunks",
    description=(
        "Loads the parsed pages for a document from metadata/parsed/, splits "
        "the text recursively using RecursiveCharacterTextSplitter "
        "(500 chars, 100 overlap), validates each chunk, and writes a "
        "chunks.json file to metadata/chunks/. Returns the full chunk list "
        "with statistics."
    ),
)
async def chunk_document(
    document_id: str,
    service: ChunkingService = Depends(get_chunking_service),
) -> ChunkingResponseSchema:
    """
    Trigger chunking for a single document by its UUID.

    Args:
        document_id: UUID of the document (must have been parsed first).
        service:     Injected ChunkingService instance.

    Returns:
        ChunkingResponseSchema with status, statistics, and chunks list.

    Raises:
        HTTPException(400): If chunking fails due to bad input.
        HTTPException(404): If no parsed JSON exists for the document.
        HTTPException(500): For unexpected server errors.
    """
    settings = get_settings()
    parsed_dir = Path(settings.metadata_path) / "parsed"

    try:
        chunks, stats = service.chunk_by_document_id(
            document_id=document_id,
            parsed_dir=parsed_dir,
        )
    except ChunkingError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Parsed pages for document '{document_id}' not found. Run parser first.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected chunking error: {exc}",
        ) from exc

    # Map domain entities → response schemas
    chunk_schemas = [
        ChunkSchema(
            chunk_id=c.chunk_id,
            document_name=c.document_name,
            page=c.page_number,
            category=c.category,
            text=c.text,
        )
        for c in chunks
    ]

    stats_schema = ChunkStatisticsSchema(
        document_id=stats.document_id,
        document_name=stats.document_name,
        total_chunks=stats.total_chunks,
        avg_chunk_size=stats.avg_chunk_size,
        max_chunk_size=stats.max_chunk_size,
        min_chunk_size=stats.min_chunk_size,
        chunks_per_page={str(k): v for k, v in stats.chunks_per_page.items()},
        processed_at=stats.processed_at,
    )

    return ChunkingResponseSchema(
        document_id=document_id,
        document_name=stats.document_name,
        status="success",
        statistics=stats_schema,
        chunks=chunk_schemas,
    )


@router.get(
    "/output/{document_id}",
    response_model=List[ChunkSchema],
    summary="Retrieve previously generated chunks for a document",
    description=(
        "Reads the chunks.json file from metadata/chunks/ for the given document "
        "and returns the list of chunk records. Run POST /chunker/chunk/{document_id} "
        "first to generate the output."
    ),
)
async def get_chunks_output(
    document_id: str,
) -> List[ChunkSchema]:
    """
    Retrieve the chunks.json output for a previously chunked document.

    Args:
        document_id: UUID of the document.

    Returns:
        List of ChunkSchema records.

    Raises:
        HTTPException(404): If no chunks JSON exists for the document.
        HTTPException(500): If the chunks JSON cannot be read or parsed.
    """
    settings = get_settings()
    json_path = Path(settings.metadata_path) / "chunks" / f"{document_id}_chunks.json"

    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Chunks output for document '{document_id}' not found. "
                f"Run POST /chunker/chunk/{document_id} first."
            ),
        )

    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        # Support envelope format ({"metadata": ..., "chunks": [...]}) and flat list
        chunk_records = data.get("chunks", data) if isinstance(data, dict) else data

        return [
            ChunkSchema(
                chunk_id=record["chunk_id"],
                document_name=record["document_name"],
                page=record["page"],
                category=record["category"],
                text=record["text"],
            )
            for record in chunk_records
        ]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read chunks output: {exc}",
        ) from exc


@router.post(
    "/chunk/batch",
    response_model=GlobalChunkStatsSchema,
    summary="Chunk multiple parsed documents in a batch",
    description=(
        "Processes a list of document UUIDs sequentially. "
        "Each document must have a parsed JSON in metadata/parsed/. "
        "Returns global statistics across all processed documents."
    ),
)
async def chunk_documents_batch(
    document_ids: List[str] = Body(
        ...,
        description="List of document UUIDs to process.",
        examples=[["1808ca0c-57c1-517c-9af0-66fb7f1510d9"]],
    ),
    service: ChunkingService = Depends(get_chunking_service),
) -> GlobalChunkStatsSchema:
    """
    Trigger batch chunking for multiple documents.

    Args:
        document_ids: List of document UUIDs.
        service:      Injected ChunkingService instance.

    Returns:
        GlobalChunkStatsSchema with aggregated statistics.

    Raises:
        HTTPException(400): If document_ids list is empty.
        HTTPException(500): For unexpected server errors.
    """
    if not document_ids:
        raise HTTPException(
            status_code=400,
            detail="document_ids list must not be empty.",
        )

    settings = get_settings()
    parsed_dir = Path(settings.metadata_path) / "parsed"

    try:
        global_stats = service.chunk_multiple_documents(
            document_ids=document_ids,
            parsed_dir=parsed_dir,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Batch chunking failed: {exc}",
        ) from exc

    return GlobalChunkStatsSchema(
        total_documents=global_stats.total_documents,
        total_chunks=global_stats.total_chunks,
        avg_chunk_size=global_stats.avg_chunk_size,
        max_chunk_size=global_stats.max_chunk_size,
        min_chunk_size=global_stats.min_chunk_size,
        chunks_per_document=global_stats.chunks_per_document,
        failed_documents=global_stats.failed_documents,
        run_started_at=global_stats.run_started_at,
        run_completed_at=global_stats.run_completed_at,
    )
