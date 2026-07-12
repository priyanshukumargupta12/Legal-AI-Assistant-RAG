"""
app/elasticsearch/elastic_schemas.py
=====================================
Pydantic V2 schemas for Elasticsearch API boundaries.

PURPOSE:
    Defines request/response schemas for the Elasticsearch controller layer.
    These are never used inside the service/repository layers — only at the
    FastAPI boundary where serialisation is required.

DESIGN:
    - Pydantic V2 (model_config = ConfigDict)
    - Field-level validation and descriptions for OpenAPI docs
    - All schemas are immutable (frozen=True) for safety

SOLID: Single Responsibility — only data serialisation/validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ElasticsearchSearchRequest(BaseModel):
    """
    Request schema for a BM25 keyword search.

    Attributes:
        query:           Full-text search query string.
        top_k:           Maximum number of results to return (default: 10).
        category_filter: Optional category to restrict results to.
        document_filter: Optional document_id to restrict results to.
        fuzzy:           If True, enables fuzzy matching for typo-tolerance.
    """

    model_config = ConfigDict(frozen=True)

    query: str = Field(..., min_length=1, max_length=2000, description="BM25 search query")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    category_filter: Optional[str] = Field(default=None, description="Filter by document category")
    document_filter: Optional[str] = Field(default=None, description="Filter by document_id")
    fuzzy: bool = Field(default=False, description="Enable fuzzy (typo-tolerant) matching")


class ElasticsearchSearchResultSchema(BaseModel):
    """
    Schema for a single BM25 search result returned by the API.

    Attributes:
        chunk_id:      Unique chunk identifier.
        document_id:   Parent document UUID.
        document_name: Source PDF filename.
        category:      Document category.
        page_number:   Source page number (1-based).
        chunk_index:   Chunk position within the document.
        chunk_text:    Full text of the matched chunk.
        score:         Raw BM25 relevance score.
        rank:          Result rank (1 = most relevant).
        source:        Always "keyword".
        metadata:      Arbitrary metadata dict from the chunk.
    """

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    document_name: str
    category: str
    page_number: int
    chunk_index: int
    chunk_text: str
    score: float
    rank: int
    source: str = "keyword"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ElasticsearchSearchResponse(BaseModel):
    """
    Response schema wrapping a list of BM25 search results.

    Attributes:
        query:        The original search query string.
        total_hits:   Total number of matching documents in the index.
        results:      Ordered list of top-K search result documents.
        latency_ms:   Query processing time in milliseconds.
    """

    model_config = ConfigDict(frozen=True)

    query: str
    total_hits: int
    results: List[ElasticsearchSearchResultSchema]
    latency_ms: float


class ElasticsearchStatisticsSchema(BaseModel):
    """
    Schema for exposing bulk indexing run statistics via the API.

    Attributes:
        total_chunks:     Total chunks attempted during the run.
        indexed_chunks:   Successfully indexed chunks.
        failed_chunks:    Chunks that failed during bulk indexing.
        index_name:       Elasticsearch target index name.
        total_duration_s: Total wall-clock time in seconds.
        avg_chunk_time_ms: Average processing time per chunk in ms.
        processed_at:     Timestamp of the indexing run.
    """

    model_config = ConfigDict(frozen=True)

    total_chunks: int
    indexed_chunks: int
    failed_chunks: int
    index_name: str
    total_duration_s: float
    avg_chunk_time_ms: float
    processed_at: datetime
