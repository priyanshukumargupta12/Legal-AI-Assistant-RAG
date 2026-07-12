"""
app/retrieval/retrieval_models.py
=====================================
Pure-Python dataclasses for the Hybrid Retrieval subsystem.

PURPOSE:
    Domain models representing query inputs, fusion results, and final
    retrieval outputs. No framework dependencies — only stdlib dataclasses.

WHY HYBRID RETRIEVAL?
----------------------
1.  **Vector-Only Limitations:**
    Dense semantic search excels at conceptual similarity ("retirement savings"
    matches "401(k) plans") but can miss exact terminology. Legal documents
    require precise term matching for statute citations (§ 162), case references
    (OLC-2026), and regulatory codes that embeddings may misrepresent.

2.  **BM25-Only Limitations:**
    Pure keyword search cannot handle paraphrasing, synonyms, or contextual
    meaning. A query about "tax avoidance" may miss "tax evasion" documents
    that are semantically identical but lexically different.

3.  **Hybrid = Best of Both Worlds:**
    Combining dense vector retrieval (Qdrant) with sparse BM25 (Elasticsearch)
    achieves superior recall and precision across both lexically exact and
    semantically related queries.

4.  **Weighted Rank Fusion (WRF):**
    WRF assigns configurable weights (default: 70% vector, 30% BM25) to
    normalize and combine scores from both retrievers into a single ranked list.
    This outperforms using either retriever alone for legal domain Q&A.

5.  **Metadata Filtering:**
    Legal users often need to scope retrieval to a specific category (e.g.,
    "Tax" only) or document. Pre-filtering eliminates irrelevant results before
    fusion, improving precision without sacrificing recall within the scope.

6.  **Duplicate Removal:**
    The same chunk may appear in both vector and keyword results. Deduplication
    ensures the LLM receives unique context windows, avoiding token waste and
    repetitive citations.

SOLID: Each dataclass has exactly one responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RetrievalQuery:
    """
    Validated, preprocessed user query ready for retrieval.

    Attributes:
        raw_query:       Original query string from the user.
        clean_query:     Preprocessed/normalised query string.
        top_k:           Number of results each retriever should return.
        final_top_k:     Number of results to return after fusion.
        category_filter: Optional legal category to restrict search to.
        document_filter: Optional document_id to restrict search to.
        fuzzy:           Whether to enable fuzzy BM25 matching.
    """

    raw_query: str
    clean_query: str
    top_k: int = 10
    final_top_k: int = 5
    category_filter: Optional[str] = None
    document_filter: Optional[str] = None
    fuzzy: bool = False


@dataclass
class FusionCandidate:
    """
    Intermediate ranked candidate produced during Weighted Rank Fusion.

    Attributes:
        chunk_id:       Unique chunk identifier (deduplication key).
        document_id:    Parent document UUID.
        document_name:  Source PDF filename.
        category:       Document category.
        page_number:    Source page number (1-based).
        chunk_index:    Position within the document.
        text:           Chunk text content.
        vector_score:   Raw cosine similarity score from Qdrant (0–1).
        bm25_score:     Raw BM25 relevance score from Elasticsearch.
        vector_rank:    Rank in the vector result list (1 = best, 0 = absent).
        bm25_rank:      Rank in the BM25 result list (1 = best, 0 = absent).
        hybrid_score:   Final weighted fusion score.
        metadata:       Preserved chunk metadata dict.
    """

    chunk_id: str
    document_id: str
    document_name: str
    category: str
    page_number: int
    chunk_index: int
    text: str
    vector_score: float = 0.0
    bm25_score: float = 0.0
    vector_rank: int = 0
    bm25_rank: int = 0
    hybrid_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridRetrievalResult:
    """
    Final output of the Hybrid Retrieval Engine for a single query.

    Attributes:
        query:           Preprocessed query string.
        results:         Ordered list of top-K ``FusionCandidate`` objects.
        vector_count:    Number of results returned by Qdrant.
        bm25_count:      Number of results returned by Elasticsearch.
        total_candidates: Total unique candidates before final top-K selection.
        retrieval_time_ms: Wall-clock retrieval time in milliseconds.
        retrieved_at:    UTC timestamp of the retrieval run.
    """

    query: str
    results: List[FusionCandidate]
    vector_count: int
    bm25_count: int
    total_candidates: int
    retrieval_time_ms: float
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
