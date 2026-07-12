"""
app/elasticsearch/elastic_models.py
=====================================
Pure-Python dataclasses for the Elasticsearch subsystem.

PURPOSE:
    Defines internal domain models used by the Elasticsearch service and
    repository layers. No framework dependencies — only stdlib dataclasses.

WHY BM25 / ELASTICSEARCH FOR LEGAL DOCUMENTS?
----------------------------------------------
1.  **Keyword Precision:** Legal documents contain exact terminology — statute
    sections (§ 401(k)), case citations, jurisdiction codes — where BM25
    word frequency scoring outperforms dense vector cosine similarity.

2.  **Exact & Phrase Match:** Lawyers search for precise phrases such as
    "breach of fiduciary duty" or "Internal Revenue Code Section 162".
    BM25 ranks documents containing the exact phrase higher.

3.  **Vector Search Limitations:** Dense embeddings capture semantic meaning
    but can miss exact matches (e.g., "ERISA" and "Employee Retirement Income
    Security Act" may not score identically even though they are the same thing
    in legal context). Keyword search catches these gaps.

4.  **Metadata Filtering:** Elasticsearch provides first-class support for
    structured filters (category, document_id, page_number) with zero
    performance penalty when combined with full-text BM25 search.

5.  **Hybrid RAG:** Qdrant (dense) + Elasticsearch (sparse/BM25) are merged
    via Reciprocal Rank Fusion in the retrieval layer. Neither alone is
    sufficient for production-grade legal search.

SOLID: Each dataclass has exactly one responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ElasticsearchDocument:
    """
    Internal representation of a chunk document ready to be indexed into
    Elasticsearch. Mirrors the Elasticsearch index mapping exactly.

    Attributes:
        chunk_id:      Deterministic UUID5 — used as the ES document ``_id``.
        document_id:   Parent document UUID (keyword filter field).
        document_name: Human-readable source PDF name (for display).
        category:      Dataset category (Acts / CourtJudgement / Tax / Legal_opinion).
        page_number:   Source page number (1-based).
        chunk_index:   Position of this chunk within the document (0-based).
        chunk_text:    Full text content of the chunk (BM25-indexed).
        source:        Retrieval source tag — always "keyword" for ES results.
        metadata:      Arbitrary key-value metadata preserved from chunking.
        indexed_at:    UTC timestamp when the document was indexed.
    """

    chunk_id: str
    document_id: str
    document_name: str
    category: str
    page_number: int
    chunk_index: int
    chunk_text: str
    source: str = "keyword"
    metadata: Dict[str, Any] = field(default_factory=dict)
    indexed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ElasticsearchSearchResult:
    """
    A single BM25 keyword search result returned by Elasticsearch.

    Attributes:
        chunk_id:      Unique identifier of the matched chunk.
        document_id:   Parent document UUID.
        document_name: Source PDF filename.
        category:      Document category.
        page_number:   Source page number (1-based).
        chunk_index:   Chunk position within the document.
        chunk_text:    Full text content of the matched chunk.
        score:         Raw BM25 relevance score from Elasticsearch.
        rank:          Position in the ranked results list (1-indexed).
        source:        Always "keyword" for Elasticsearch results.
        metadata:      Preserved chunk metadata dict.
    """

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
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ElasticsearchStatistics:
    """
    Aggregated statistics for a bulk indexing run.

    Persisted as ``metadata/elasticsearch_statistics.json`` at the end of
    every batch indexing script run.

    Attributes:
        total_chunks:        Total chunks submitted for indexing.
        indexed_chunks:      Chunks successfully written to Elasticsearch.
        failed_chunks:       Chunks that failed due to bulk errors.
        index_name:          Target Elasticsearch index name.
        total_duration_s:    Wall-clock time for the entire run (seconds).
        avg_chunk_time_ms:   Average processing time per chunk (milliseconds).
        processed_at:        UTC timestamp of the run.
    """

    total_chunks: int
    indexed_chunks: int
    failed_chunks: int
    index_name: str
    total_duration_s: float
    avg_chunk_time_ms: float
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
