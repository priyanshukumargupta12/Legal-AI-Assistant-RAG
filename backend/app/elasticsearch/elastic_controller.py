"""
app/elasticsearch/elastic_controller.py
=========================================
FastAPI controller (router) for Elasticsearch endpoints.

DEPRECATION WARNING:
    This controller is legacy dead code.
    Active API routes for Elasticsearch are aggregated in:
        app/api/routes/elasticsearch.py
    Refer to that module for production endpoints.

PURPOSE:
    Exposes REST API endpoints for:
        - POST /elasticsearch/search    — BM25 keyword search
        - GET  /elasticsearch/health    — cluster health check
        - GET  /elasticsearch/stats     — index document/storage statistics

NOTE: Indexing (bulk upload) is an offline batch operation handled by
      ``scripts/batch_index_elasticsearch.py``. No indexing endpoint is
      exposed to avoid accidental data loss via the API.

DESIGN:
    - FastAPI APIRouter with prefix ``/elasticsearch``.
    - Depends on ``ElasticsearchService`` via FastAPI's DI system.
    - Returns Pydantic V2 response schemas for clean OpenAPI docs.

SOLID: Single Responsibility — only handles HTTP request/response translation.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.exceptions import KeywordStoreError
from app.elasticsearch.elastic_client import get_elasticsearch_client
from app.elasticsearch.elastic_repository import ElasticsearchRepository
from app.elasticsearch.elastic_schemas import (
    ElasticsearchSearchRequest,
    ElasticsearchSearchResponse,
    ElasticsearchSearchResultSchema,
)
from app.elasticsearch.elastic_service import ElasticsearchService

router = APIRouter(prefix="/elasticsearch", tags=["Elasticsearch"])


# ── Dependency factories ────────────────────────────────────────────────────────


def get_es_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ElasticsearchService:
    """Dependency: construct a ready-to-use ElasticsearchService."""
    client = get_elasticsearch_client(settings)
    repo = ElasticsearchRepository(client=client, settings=settings)
    metadata_dir = Path(settings.metadata_path)
    return ElasticsearchService(repository=repo, metadata_dir=metadata_dir)


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post(
    "/search",
    response_model=ElasticsearchSearchResponse,
    summary="BM25 Keyword Search",
    description=(
        "Perform a BM25 keyword search over all indexed legal document chunks. "
        "Supports optional category and document filters, fuzzy matching, and "
        "phrase boosting. Returns ranked top-K results with BM25 scores."
    ),
)
async def keyword_search(
    request: ElasticsearchSearchRequest,
    service: Annotated[ElasticsearchService, Depends(get_es_service)],
) -> ElasticsearchSearchResponse:
    """
    BM25 keyword search endpoint.

    Args:
        request: Search parameters (query, top_k, filters, fuzzy flag).
        service: Injected ElasticsearchService instance.

    Returns:
        ElasticsearchSearchResponse with ranked results.

    Raises:
        HTTP 503: If Elasticsearch is unreachable.
        HTTP 500: On unexpected search errors.
    """
    t0 = time.perf_counter()
    try:
        results = await service.keyword_search(
            query=request.query,
            top_k=request.top_k,
            category_filter=request.category_filter,
            document_filter=request.document_filter,
            fuzzy=request.fuzzy,
        )
    except KeywordStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    latency_ms = (time.perf_counter() - t0) * 1000
    return ElasticsearchSearchResponse(
        query=request.query,
        total_hits=len(results),
        results=[
            ElasticsearchSearchResultSchema(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_name=r.document_name,
                category=r.category,
                page_number=r.page_number,
                chunk_index=r.chunk_index,
                chunk_text=r.text,
                score=r.score,
                rank=r.rank,
                source=r.source,
                metadata={},
            )
            for r in results
        ],
        latency_ms=round(latency_ms, 2),
    )


@router.get(
    "/health",
    summary="Elasticsearch Health Check",
    description="Returns the connectivity status of the Elasticsearch cluster.",
)
async def health_check(
    service: Annotated[ElasticsearchService, Depends(get_es_service)],
) -> Dict[str, Any]:
    """Check if Elasticsearch is reachable."""
    healthy = await service.health_check()
    if not healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Elasticsearch cluster is not reachable.",
        )
    return {"status": "healthy", "store": "elasticsearch"}


@router.get(
    "/stats",
    summary="Index Statistics",
    description="Returns the document count and store size for the legal_documents index.",
)
async def index_stats(
    service: Annotated[ElasticsearchService, Depends(get_es_service)],
) -> Dict[str, Any]:
    """Return Elasticsearch index statistics."""
    return service.get_index_stats()
