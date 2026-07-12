"""
app/retrieval/retrieval_repository.py
========================================
Data-access layer for the Hybrid Retrieval Engine.

PURPOSE:
    Provides thin wrapper methods over the existing ``VectorRepository`` and
    ``KeywordRepository`` abstractions, adding:
        - Per-retriever error isolation (one retriever down ≠ total failure)
        - Consistent logging of retriever timings
        - Timeout enforcement per retriever

DESIGN:
    - Depends on ``VectorRepository`` (Qdrant) and ``KeywordRepository`` (ES)
      via constructor injection — satisfying Dependency Inversion.
    - Each retriever call is wrapped in try/except and returns an empty list
      on failure rather than raising — the service layer logs the partial result.
    - Implements ``asyncio.gather`` for concurrent execution.

SOLID:
    Single Responsibility — only performs retriever I/O.
    Dependency Inversion  — depends on abstract repository interfaces.
    Open/Closed          — adding a new retriever (e.g., Weaviate) requires
                           only a new method, not modifying existing ones.
"""

from __future__ import annotations

import asyncio
import time
from typing import List, Optional

from app.core.exceptions import VectorStoreError, KeywordStoreError
from app.models.document import RetrievedChunk
from app.repositories.keyword_repository import KeywordRepository
from app.repositories.vector_repository import VectorRepository
from app.retrieval.retrieval_logger import retrieval_log
from app.retrieval.retrieval_utils import with_timeout


class HybridRetrievalRepository:
    """
    Data-access layer combining Qdrant (vector) and Elasticsearch (BM25).

    Both retrievers are called concurrently via ``asyncio.gather``.
    If one retriever is unavailable, the other continues and returns partial
    results rather than failing the entire retrieval request.

    Args:
        vector_repo:    Concrete ``VectorRepository`` (e.g., ``QdrantRepository``).
        keyword_repo:   Concrete ``KeywordRepository`` (e.g., ``ElasticsearchRepository``).
        timeout_s:      Per-retriever timeout in seconds (default: 10.0).
    """

    def __init__(
        self,
        vector_repo: VectorRepository,
        keyword_repo: KeywordRepository,
        timeout_s: float = 10.0,
    ) -> None:
        self._vector_repo = vector_repo
        self._keyword_repo = keyword_repo
        self._timeout_s = timeout_s

    async def vector_search(
        self,
        query_vector: List[float],
        top_k: int,
        category_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Execute a vector similarity search against Qdrant.

        Args:
            query_vector:    384-dimensional query embedding.
            top_k:           Number of results to return.
            category_filter: Optional category to pre-filter.

        Returns:
            List of ``RetrievedChunk`` objects ordered by cosine similarity.
            Empty list if Qdrant is unreachable or times out.
        """
        t0 = time.perf_counter()
        retrieval_log.info(
            "Vector search start | top_k={k} | category={cat}",
            k=top_k,
            cat=category_filter or "all",
        )

        try:
            results = await with_timeout(
                self._vector_repo.search(
                    query_vector=query_vector,
                    top_k=top_k,
                    category_filter=category_filter,
                ),
                timeout_s=self._timeout_s,
                fallback=[],
                label="vector_search",
            )
            results = results or []
        except (VectorStoreError, Exception) as exc:
            retrieval_log.error(
                "Vector search failed | error={err}", err=str(exc)
            )
            results = []

        elapsed_ms = (time.perf_counter() - t0) * 1000
        retrieval_log.info(
            "Vector search done | results={n} | latency={lat:.1f}ms",
            n=len(results),
            lat=elapsed_ms,
        )
        return results

    async def bm25_search(
        self,
        query: str,
        top_k: int,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None,
        fuzzy: bool = False,
    ) -> List[RetrievedChunk]:
        """
        Execute a BM25 keyword search against Elasticsearch.

        Args:
            query:           Preprocessed text query.
            top_k:           Number of results to return.
            category_filter: Optional category to filter.
            document_filter: Optional document_id to filter.
            fuzzy:           Enable fuzzy matching.

        Returns:
            List of ``RetrievedChunk`` objects ordered by BM25 score.
            Empty list if Elasticsearch is unreachable or times out.
        """
        t0 = time.perf_counter()
        retrieval_log.info(
            "BM25 search start | query={q} | top_k={k} | fuzzy={fz}",
            q=query[:60],
            k=top_k,
            fz=fuzzy,
        )

        try:
            results = await with_timeout(
                self._keyword_repo.search(
                    query=query,
                    top_k=top_k,
                    category_filter=category_filter,
                ),
                timeout_s=self._timeout_s,
                fallback=[],
                label="bm25_search",
            )
            results = results or []
        except (KeywordStoreError, Exception) as exc:
            retrieval_log.error(
                "BM25 search failed | error={err}", err=str(exc)
            )
            results = []

        elapsed_ms = (time.perf_counter() - t0) * 1000
        retrieval_log.info(
            "BM25 search done | results={n} | latency={lat:.1f}ms",
            n=len(results),
            lat=elapsed_ms,
        )
        return results

    async def parallel_search(
        self,
        query_vector: List[float],
        query_text: str,
        top_k: int,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None,
        fuzzy: bool = False,
    ) -> tuple[List[RetrievedChunk], List[RetrievedChunk]]:
        """
        Fire vector and BM25 searches concurrently and return both result lists.

        Uses ``asyncio.gather`` to execute both retrievers in parallel, reducing
        total retrieval latency to approximately max(vector_time, bm25_time)
        instead of the sum.

        Args:
            query_vector:    Dense query embedding for Qdrant.
            query_text:      Preprocessed text query for Elasticsearch.
            top_k:           Results per retriever.
            category_filter: Shared category filter applied to both retrievers.
            document_filter: Shared document filter applied to Elasticsearch.
            fuzzy:           BM25 fuzzy flag.

        Returns:
            Tuple of (vector_results, bm25_results).
        """
        t0 = time.perf_counter()
        retrieval_log.info(
            "Parallel search start | top_k={k} | cat={cat}",
            k=top_k,
            cat=category_filter or "all",
        )

        vector_results, bm25_results = await asyncio.gather(
            self.vector_search(
                query_vector=query_vector,
                top_k=top_k,
                category_filter=category_filter,
            ),
            self.bm25_search(
                query=query_text,
                top_k=top_k,
                category_filter=category_filter,
                document_filter=document_filter,
                fuzzy=fuzzy,
            ),
            return_exceptions=False,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        retrieval_log.info(
            "Parallel search done | vector={v} | bm25={b} | latency={lat:.1f}ms",
            v=len(vector_results),
            b=len(bm25_results),
            lat=elapsed_ms,
        )
        return vector_results, bm25_results

    async def health_check(self) -> dict:
        """
        Check health of both retrievers concurrently.

        Returns:
            Dict with ``vector`` and ``keyword`` health statuses.
        """
        vector_ok, keyword_ok = await asyncio.gather(
            self._vector_repo.health_check(),
            self._keyword_repo.health_check(),
        )
        return {
            "vector_store": "healthy" if vector_ok else "unavailable",
            "keyword_store": "healthy" if keyword_ok else "unavailable",
        }
