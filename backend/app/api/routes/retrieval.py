"""
app/api/routes/retrieval.py
===========================
FastAPI routes for Hybrid Retrieval (semantic vector + BM25 keyword search).
"""

from __future__ import annotations

from typing import Annotated, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies.services import get_retrieval_service
from app.api.responses.standard_response import StandardResponse
from app.retrieval.retrieval_service import HybridRetrievalService

router = APIRouter(prefix="/search", tags=["Hybrid Retrieval"])


class SearchRequest(BaseModel):
    """Schema for a search query request."""
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language search query")
    category_filter: Optional[str] = Field(default=None, description="Optional legal category filter")
    top_k: Optional[int] = Field(default=10, ge=1, le=100, description="Results to fetch per retriever")


@router.post(
    "",
    response_model=StandardResponse,
    summary="Hybrid Semantic and Keyword Search",
    description="Query Qdrant (semantic vector search) and Elasticsearch (BM25) in parallel and fuse results using Weighted Rank Fusion.",
)
async def hybrid_search(
    request: SearchRequest,
    service: Annotated[HybridRetrievalService, Depends(get_retrieval_service)],
) -> StandardResponse:
    """
    Executes parallel search and returns the top 5 fused chunks.
    """
    result = await service.retrieve(
        raw_query=request.query,
        top_k=request.top_k or 10,
        final_top_k=5,  # Specified requirement: top 5 retrieved chunks
        category_filter=request.category_filter,
    )

    fused_chunks = []
    for rank, c in enumerate(result.results, start=1):
        fused_chunks.append({
            "chunk_id": c.chunk_id,
            "document": c.document_name,
            "page": c.page_number,
            "category": c.category,
            "text": c.text,
            "vector_score": round(c.vector_score, 4),
            "bm25_score": round(c.bm25_score, 4),
            "hybrid_score": round(c.hybrid_score, 4)
        })

    data = {
        "query": result.query,
        "results": fused_chunks,
        "vector_count": result.vector_count,
        "bm25_count": result.bm25_count,
        "total_candidates": result.total_candidates,
        "retrieval_time_ms": result.retrieval_time_ms
    }

    return StandardResponse.success(
        data=data,
        message="Hybrid retrieval search completed successfully."
    )
