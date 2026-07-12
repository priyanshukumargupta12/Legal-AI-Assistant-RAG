"""
app/retrieval/retrieval_controller.py
=====================================
HTTP controller for the Retrieval subsystem.

DEPRECATION WARNING:
    This controller is legacy dead code.
    Active API routes for search and hybrid retrieval are aggregated in:
        app/api/routes/retrieval.py
    Refer to that module for production endpoints.

PURPOSE:
    Exposes REST API endpoints for:
        - POST /retrieval/search   — Full hybrid search (vector + BM25 + WRF)
        - GET  /retrieval/health   — Health check for both retrievers

DESIGN:
    - FastAPI APIRouter with prefix ``/retrieval``.
    - Depends on ``HybridRetrievalService`` via FastAPI's DI.
    - Maps ``HybridRetrievalResult`` domain objects → Pydantic response schemas.
    - Translates domain exceptions to HTTP error codes.

SOLID: Single Responsibility — HTTP request/response translation only.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.exceptions import RetrievalError
from app.elasticsearch.elastic_client import get_elasticsearch_client
from app.elasticsearch.elastic_repository import ElasticsearchRepository
from app.embeddings.embedder import BGEEmbedder
from app.retrieval.hybrid_ranker import WeightedRankFuser
from app.retrieval.retrieval_repository import HybridRetrievalRepository
from app.retrieval.retrieval_schemas import (
    HybridSearchRequest,
    HybridSearchResponse,
    RetrievalResultSchema,
)
from app.retrieval.retrieval_service import HybridRetrievalService
from app.retrieval.retrieval_utils import format_score
from app.vectorstore import get_qdrant_client, QdrantRepository

router = APIRouter(prefix="/retrieval", tags=["Hybrid Retrieval"])


# ── Dependency factories ───────────────────────────────────────────────────────


def get_retrieval_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HybridRetrievalService:
    """Construct a fully wired HybridRetrievalService for each request."""

    # Vector retriever
    qdrant_client = get_qdrant_client(settings)
    vector_repo = QdrantRepository(client=qdrant_client, settings=settings)

    # Keyword retriever
    es_client = get_elasticsearch_client(settings)
    keyword_repo = ElasticsearchRepository(client=es_client, settings=settings)

    # Repository layer (combines both)
    retrieval_repo = HybridRetrievalRepository(
        vector_repo=vector_repo,
        keyword_repo=keyword_repo,
        timeout_s=settings.retrieval_timeout_s,
    )

    # Embedder (singleton — loaded once)
    embedder = BGEEmbedder(
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_cache_dir,
    )

    # Determine weights from request or fall back to settings
    fuser = WeightedRankFuser(
        vector_weight=settings.vector_weight,
        bm25_weight=settings.bm25_weight,
    )

    return HybridRetrievalService(
        repository=retrieval_repo,
        embedder=embedder,
        fuser=fuser,
        retrieval_top_k=settings.retrieval_top_k,
        final_top_k=settings.retrieval_final_top_k,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post(
    "/search",
    response_model=HybridSearchResponse,
    summary="Hybrid Semantic + Keyword Search",
    description=(
        "Execute a hybrid retrieval combining Qdrant vector search and "
        "Elasticsearch BM25 keyword search. Results are fused using Weighted "
        "Rank Fusion and returned as a ranked Top-K list with individual "
        "vector, BM25, and hybrid scores."
    ),
)
async def hybrid_search(
    request: HybridSearchRequest,
    service: Annotated[HybridRetrievalService, Depends(get_retrieval_service)],
) -> HybridSearchResponse:
    """
    Hybrid search endpoint: vector + BM25 → WRF → Top-K.

    Raises:
        HTTP 422: If query validation fails.
        HTTP 503: If both retrievers are unreachable.
        HTTP 500: On unexpected errors.
    """
    try:
        result = await service.retrieve(
            raw_query=request.query,
            top_k=request.top_k,
            final_top_k=request.final_top_k,
            category_filter=request.category_filter,
            document_filter=request.document_filter,
            fuzzy=request.fuzzy,
        )
    except RetrievalError as exc:
        if "validation" in str(exc).lower() or "empty" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return HybridSearchResponse(
        query=result.query,
        results=[
            RetrievalResultSchema(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document=c.document_name,
                page=c.page_number,
                category=c.category,
                text=c.text,
                vector_score=format_score(c.vector_score),
                bm25_score=format_score(c.bm25_score),
                hybrid_score=format_score(c.hybrid_score),
                metadata=c.metadata,
            )
            for c in result.results
        ],
        vector_count=result.vector_count,
        bm25_count=result.bm25_count,
        total_candidates=result.total_candidates,
        retrieval_time_ms=result.retrieval_time_ms,
        retrieved_at=result.retrieved_at,
    )


@router.get(
    "/health",
    summary="Retrieval Health Check",
    description="Check connectivity of both Qdrant and Elasticsearch retrievers.",
)
async def health_check(
    service: Annotated[HybridRetrievalService, Depends(get_retrieval_service)],
) -> Dict[str, Any]:
    """Return health status of both retrieval backends."""
    health = await service.health_check()
    all_healthy = all(v == "healthy" for v in health.values())
    if not all_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "One or more retrieval backends are unavailable.",
                "status": health,
            },
        )
    return {"status": "healthy", **health}
