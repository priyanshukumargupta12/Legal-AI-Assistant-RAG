"""
app/retrieval/retrieval_schemas.py
=====================================
Pydantic V2 schemas for the Hybrid Retrieval API boundary.

PURPOSE:
    Defines request/response schemas for the retrieval controller layer.
    These are used only at the FastAPI boundary — never inside service/
    repository layers — for clean serialisation and OpenAPI documentation.

DESIGN:
    - Pydantic V2 (model_config = ConfigDict)
    - All schemas are frozen (immutable) for safety
    - Field-level validation and descriptions

SOLID: Single Responsibility — data serialisation/validation only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HybridSearchRequest(BaseModel):
    """
    Request schema for a hybrid (vector + BM25) search query.

    Attributes:
        query:           Natural language user query string.
        top_k:           Results to fetch from each retriever (default: 10).
        final_top_k:     Results to return after fusion (default: 5).
        category_filter: Optional legal category filter.
        document_filter: Optional document_id filter.
        fuzzy:           Enable fuzzy BM25 matching for typo tolerance.
        vector_weight:   Custom weight for vector scores (overrides settings).
        bm25_weight:     Custom weight for BM25 scores (overrides settings).
    """

    model_config = ConfigDict(frozen=True)

    query: str = Field(..., min_length=1, max_length=2000, description="Natural language query")
    top_k: int = Field(default=10, ge=1, le=100, description="Results per retriever")
    final_top_k: int = Field(default=5, ge=1, le=20, description="Final fused results")
    category_filter: Optional[str] = Field(default=None, description="Filter by document category")
    document_filter: Optional[str] = Field(default=None, description="Filter by document_id")
    fuzzy: bool = Field(default=False, description="Enable fuzzy BM25 matching")
    vector_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Vector score weight (0–1)")
    bm25_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="BM25 score weight (0–1)")


class RetrievalResultSchema(BaseModel):
    """
    Schema for a single fused retrieval result.

    This is the output format specified in the user's requirements:
        {
            "chunk_id": "...",
            "document": "...",
            "page": 23,
            "category": "Tax",
            "text": "...",
            "vector_score": 0.92,
            "bm25_score": 13.6,
            "hybrid_score": 0.95
        }
    """

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    document: str = Field(description="Source document filename")
    page: int = Field(description="Source page number (1-based)")
    category: str
    text: str = Field(description="Full chunk text content")
    vector_score: float = Field(description="Raw cosine similarity from Qdrant")
    bm25_score: float = Field(description="Raw BM25 score from Elasticsearch")
    hybrid_score: float = Field(description="Final weighted fusion score")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HybridSearchResponse(BaseModel):
    """
    Response schema for the hybrid search endpoint.

    Attributes:
        query:              Preprocessed query string.
        results:            Ordered top-K fused results.
        vector_count:       Results returned by Qdrant.
        bm25_count:         Results returned by Elasticsearch.
        total_candidates:   Unique candidates before top-K selection.
        retrieval_time_ms:  End-to-end retrieval latency in ms.
        retrieved_at:       UTC timestamp.
    """

    model_config = ConfigDict(frozen=True)

    query: str
    results: List[RetrievalResultSchema]
    vector_count: int
    bm25_count: int
    total_candidates: int
    retrieval_time_ms: float
    retrieved_at: datetime
