"""
app/elasticsearch/elastic_repository.py
=========================================
Elasticsearch implementation of the abstract KeywordRepository.

PURPOSE:
    Provides the concrete data-access layer for Elasticsearch operations:
        - Auto-create index with legal_analyzer mapping on startup.
        - Bulk-index ``DocumentChunk`` objects.
        - BM25 search with optional category/document filters.
        - Exact-phrase search.
        - Fuzzy search for typo tolerance.
        - Delete all chunks for a given document_id.
        - Health check.

DESIGN:
    - Synchronous Elasticsearch client (sync is simpler for batch scripts).
    - Async wrappers (run_in_executor) expose the KeywordRepository contract.
    - Index creation is idempotent — safe to call on every startup.
    - All public methods log timings for observability.

SOLID:
    Liskov Substitution  — fully satisfies ``KeywordRepository`` contract.
    Dependency Inversion — depends on abstractions (Settings, ES client).
    Single Responsibility — only performs data-access operations.
"""

from __future__ import annotations

import asyncio
import time
from functools import partial
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import BulkIndexError

from app.core.config import Settings
from app.core.exceptions import KeywordStoreConnectionError, KeywordStoreError
from app.elasticsearch.bulk_index import bulk_index_documents
from app.elasticsearch.elastic_logger import elastic_log
from app.elasticsearch.elastic_models import ElasticsearchDocument
from app.elasticsearch.elastic_utils import (
    build_bulk_actions,
    chunk_to_es_document,
    detect_duplicate_chunk_ids,
    validate_chunks_batch,
)
from app.elasticsearch.mapping import ELASTICSEARCH_INDEX_SETTINGS
from app.models.document import DocumentChunk, RetrievedChunk
from app.repositories.keyword_repository import KeywordRepository


class ElasticsearchRepository(KeywordRepository):
    """
    Concrete Elasticsearch implementation of ``KeywordRepository``.

    All public methods satisfy the async interface defined by
    ``KeywordRepository``. Heavy I/O operations are dispatched to a thread
    pool via ``asyncio.get_event_loop().run_in_executor`` so the event loop
    is never blocked.

    Args:
        client:     Configured synchronous ``Elasticsearch`` client.
        settings:   Application settings (index name, batch size, etc.).
    """

    def __init__(self, client: Elasticsearch, settings: Settings) -> None:
        self._client = client
        self._index = settings.elasticsearch_index_name
        self._batch_size = settings.elasticsearch_bulk_batch_size
        self._refresh_interval = settings.elasticsearch_refresh_interval

    # ── Index Management ───────────────────────────────────────────────────────

    def create_index_if_not_exists(self) -> bool:
        """
        Create the Elasticsearch index if it does not already exist.

        Applies the full ``ELASTICSEARCH_INDEX_SETTINGS`` mapping including
        the custom ``legal_analyzer`` and all field type definitions.

        Returns:
            True if the index was newly created.
            False if the index already existed.

        Raises:
            KeywordStoreError: On unexpected Elasticsearch API errors.
        """
        try:
            if self._client.indices.exists(index=self._index):
                elastic_log.info(
                    "Index already exists — skipping creation | index={idx}",
                    idx=self._index,
                )
                return False

            # Apply dynamic refresh interval from settings
            body = dict(ELASTICSEARCH_INDEX_SETTINGS)
            body["settings"]["refresh_interval"] = self._refresh_interval  # type: ignore[index]

            self._client.indices.create(index=self._index, body=body)
            elastic_log.info(
                "Index created successfully | index={idx}",
                idx=self._index,
            )
            return True

        except Exception as exc:
            elastic_log.error(
                "Failed to create index | index={idx} | error={err}",
                idx=self._index,
                err=str(exc),
            )
            raise KeywordStoreError(
                message=f"Failed to create Elasticsearch index '{self._index}': {exc}",
                operation="create_index",
            ) from exc

    def delete_index(self) -> None:
        """
        Delete the Elasticsearch index (destructive — use with caution).

        Raises:
            KeywordStoreError: If the delete operation fails.
        """
        try:
            self._client.indices.delete(index=self._index, ignore_unavailable=True)
            elastic_log.info("Index deleted | index={idx}", idx=self._index)
        except Exception as exc:
            raise KeywordStoreError(
                message=f"Failed to delete index '{self._index}': {exc}",
                operation="delete_index",
            ) from exc

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Return the document count and storage size for the index.

        Returns:
            Dict with ``doc_count``, ``store_size_bytes``, ``index_name``.
        """
        try:
            stats = self._client.indices.stats(index=self._index)
            total = stats["_all"]["total"]
            return {
                "index_name": self._index,
                "doc_count": total["docs"]["count"],
                "store_size_bytes": total["store"]["size_in_bytes"],
            }
        except Exception as exc:
            elastic_log.warning(
                "Could not retrieve index stats | error={err}", err=str(exc)
            )
            return {"index_name": self._index, "doc_count": 0, "store_size_bytes": 0}

    # ── Indexing ───────────────────────────────────────────────────────────────

    def _index_chunks_sync(self, chunks: List[DocumentChunk]) -> Dict[str, int]:
        """
        Synchronous implementation of bulk chunk indexing.

        Steps:
            1. Validate all chunks; collect invalid ones for logging.
            2. Detect and warn on duplicate chunk_ids.
            3. Convert valid chunks to ``ElasticsearchDocument``.
            4. Bulk-index in batches.

        Returns:
            Dict with ``indexed``, ``failed``, ``invalid`` counts.
        """
        t0 = time.perf_counter()

        # Step 1 — Validate
        valid_chunks, invalid_records = validate_chunks_batch(chunks)
        elastic_log.info(
            "Chunk validation | total={total} | valid={valid} | invalid={inv}",
            total=len(chunks),
            valid=len(valid_chunks),
            inv=len(invalid_records),
        )

        if not valid_chunks:
            elastic_log.warning("No valid chunks to index.")
            return {"indexed": 0, "failed": 0, "invalid": len(invalid_records)}

        # Step 2 — Detect duplicates
        duplicates = detect_duplicate_chunk_ids(valid_chunks)
        if duplicates:
            elastic_log.warning(
                "Duplicate chunk_ids detected | count={n} | ids={ids}",
                n=len(duplicates),
                ids=duplicates[:5],
            )

        # Step 3 — Convert to ES documents
        es_docs: List[ElasticsearchDocument] = [
            chunk_to_es_document(c) for c in valid_chunks
        ]

        # Step 4 — Bulk index
        success, errors, _ = bulk_index_documents(
            client=self._client,
            documents=es_docs,
            index_name=self._index,
            batch_size=self._batch_size,
        )

        elapsed = time.perf_counter() - t0
        elastic_log.info(
            "Indexing run complete | indexed={s} | failed={f} | time={t:.2f}s",
            s=success,
            f=errors,
            t=elapsed,
        )
        return {
            "indexed": success,
            "failed": errors + len(invalid_records),
            "invalid": len(invalid_records),
        }

    async def index_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Async interface: bulk-index document chunks into Elasticsearch.

        Args:
            chunks: List of ``DocumentChunk`` domain objects.

        Raises:
            KeywordStoreError: On bulk indexing failure.
        """
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None, partial(self._index_chunks_sync, chunks)
            )
        except Exception as exc:
            raise KeywordStoreError(
                message=f"Elasticsearch indexing failed: {exc}",
                operation="index_chunks",
            ) from exc

    # ── Search ─────────────────────────────────────────────────────────────────

    def _search_sync(
        self,
        query: str,
        top_k: int,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None,
        fuzzy: bool = False,
    ) -> List[RetrievedChunk]:
        """
        Synchronous BM25 keyword search.

        Query strategy:
            - ``match`` query on ``chunk_text`` for standard BM25 scoring.
            - ``phrase_match`` boosted sub-query to elevate exact phrase hits.
            - ``fuzzy`` option adds a fuzzy variant for typo tolerance.
            - Optional ``filter`` clauses for category and document_id.

        Args:
            query:           Full-text search string.
            top_k:           Maximum results to return.
            category_filter: Optional category keyword filter.
            document_filter: Optional document_id keyword filter.
            fuzzy:           If True, adds fuzzy matching variant.

        Returns:
            List of ``RetrievedChunk`` ordered by BM25 score (descending).
        """
        t0 = time.perf_counter()

        elastic_log.info(
            "BM25 search | query={q} | top_k={k} | category={cat} | fuzzy={fz}",
            q=query,
            k=top_k,
            cat=category_filter or "all",
            fz=fuzzy,
        )

        # ── Build the boolean query ────────────────────────────────────────────
        must_clauses: List[Dict[str, Any]] = []
        filter_clauses: List[Dict[str, Any]] = []

        # Core BM25 should clause — multi-match across chunk_text variants
        if fuzzy:
            must_clauses.append(
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["chunk_text^3", "chunk_text.exact^2", "document_name"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                        "operator": "or",
                    }
                }
            )
        else:
            # Standard BM25 — also add a phrase sub-query for boosting
            must_clauses.append(
                {
                    "bool": {
                        "should": [
                            # BM25 match
                            {
                                "match": {
                                    "chunk_text": {
                                        "query": query,
                                        "operator": "or",
                                        "boost": 1.0,
                                    }
                                }
                            },
                            # Exact phrase boost
                            {
                                "match_phrase": {
                                    "chunk_text.exact": {
                                        "query": query,
                                        "boost": 2.0,
                                    }
                                }
                            },
                            # Document name relevance
                            {
                                "match": {
                                    "document_name": {
                                        "query": query,
                                        "boost": 0.5,
                                    }
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )

        # ── Metadata filters ───────────────────────────────────────────────────
        if category_filter:
            filter_clauses.append({"term": {"category": category_filter}})
        if document_filter:
            filter_clauses.append({"term": {"document_id": document_filter}})

        es_query: Dict[str, Any] = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses,
                }
            },
            "size": top_k,
            "_source": True,
        }

        # ── Execute search ─────────────────────────────────────────────────────
        try:
            response = self._client.search(index=self._index, body=es_query)
        except Exception as exc:
            elastic_log.error(
                "Elasticsearch search failed | query={q} | error={err}",
                q=query,
                err=str(exc),
            )
            raise KeywordStoreError(
                message=f"BM25 search failed: {exc}",
                operation="search",
            ) from exc

        # ── Parse results ──────────────────────────────────────────────────────
        hits = response["hits"]["hits"]
        total_hits = response["hits"]["total"]["value"]
        elapsed_ms = (time.perf_counter() - t0) * 1000

        elastic_log.info(
            "BM25 search complete | total_hits={hits} | returned={k} | latency={lat:.1f}ms",
            hits=total_hits,
            k=len(hits),
            lat=elapsed_ms,
        )

        results: List[RetrievedChunk] = []
        for rank, hit in enumerate(hits, start=1):
            src = hit["_source"]
            page_num = src.get("page_number") or src.get("page") or src.get("metadata", {}).get("page_number")
            if page_num is None:
                raise ValueError(f"page_number is missing in Elasticsearch source for chunk {src.get('chunk_id')}")
            results.append(
                RetrievedChunk(
                    chunk_id=src.get("chunk_id", hit["_id"]),
                    document_id=src.get("document_id", ""),
                    document_name=src.get("document_name", ""),
                    category=src.get("category", ""),
                    page_number=int(page_num),
                    chunk_index=src.get("chunk_index", 0),
                    text=src.get("chunk_text", ""),
                    score=float(hit["_score"]),
                    rank=rank,
                    source="keyword",
                )
            )
        return results

    async def search(
        self,
        query: str,
        top_k: int,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None,
        fuzzy: bool = False,
    ) -> List[RetrievedChunk]:
        """
        Async BM25 keyword search with optional metadata filters.

        Args:
            query:           Full-text search query.
            top_k:           Maximum number of results.
            category_filter: Optional category keyword filter.
            document_filter: Optional document_id filter.
            fuzzy:           If True, enables fuzzy matching.

        Returns:
            List of ``RetrievedChunk`` objects ordered by score.

        Raises:
            KeywordStoreError: On search failure.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(
                self._search_sync,
                query,
                top_k,
                category_filter,
                document_filter,
                fuzzy,
            ),
        )

    # ── Delete ─────────────────────────────────────────────────────────────────

    def _delete_by_document_id_sync(self, document_id: str) -> int:
        """
        Delete all chunks belonging to ``document_id`` synchronously.

        Uses ``delete_by_query`` with a term filter — efficient even at
        large scale since it runs server-side in Elasticsearch.

        Returns:
            Number of documents deleted.
        """
        t0 = time.perf_counter()
        try:
            response = self._client.delete_by_query(
                index=self._index,
                body={"query": {"term": {"document_id": document_id}}},
                refresh=True,
            )
            deleted = response.get("deleted", 0)
            elapsed = time.perf_counter() - t0
            elastic_log.info(
                "Deleted chunks for document | document_id={did} | deleted={n} | time={t:.2f}s",
                did=document_id,
                n=deleted,
                t=elapsed,
            )
            return deleted
        except Exception as exc:
            raise KeywordStoreError(
                message=f"delete_by_query failed for document '{document_id}': {exc}",
                operation="delete_by_document_id",
            ) from exc

    async def delete_by_document_id(self, document_id: str) -> None:
        """
        Async: delete all indexed chunks for the given document.

        Args:
            document_id: UUID of the parent document.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, partial(self._delete_by_document_id_sync, document_id)
        )

    # ── Health Check ───────────────────────────────────────────────────────────

    def _health_check_sync(self) -> bool:
        """Synchronous cluster health check."""
        try:
            info = self._client.info()
            cluster_name = info.get("cluster_name", "unknown")
            version = info.get("version", {}).get("number", "unknown")
            elastic_log.info(
                "Elasticsearch healthy | cluster={c} | version={v}",
                c=cluster_name,
                v=version,
            )
            return True
        except Exception as exc:
            elastic_log.error(
                "Elasticsearch health check failed | error={err}", err=str(exc)
            )
            return False

    async def health_check(self) -> bool:
        """
        Async: return True if Elasticsearch is reachable and healthy.

        Returns:
            True if the cluster is up and responding.
            False otherwise.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._health_check_sync)
