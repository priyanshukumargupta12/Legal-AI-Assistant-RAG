"""
app/elasticsearch/elastic_service.py
======================================
Orchestration service for the Elasticsearch pipeline.

PURPOSE:
    Coordinates higher-level operations:
        - Initialising the index on startup.
        - Loading chunks from the file system.
        - Feeding them to the repository for bulk indexing.
        - Executing searches and returning structured results.
        - Generating and persisting run statistics.

DESIGN:
    - Depends on ``ElasticsearchRepository`` (via constructor injection).
    - Depends on ``FileSystemEmbeddingRepository`` for reading chunk JSON files.
    - Stateless between calls — safe for concurrent use.

SOLID:
    Single Responsibility — only orchestrates; delegates I/O to repository.
    Dependency Inversion  — depends on interfaces, not concrete classes.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.elasticsearch.elastic_logger import elastic_log
from app.elasticsearch.elastic_models import ElasticsearchStatistics
from app.elasticsearch.elastic_repository import ElasticsearchRepository
from app.models.document import DocumentChunk, RetrievedChunk


class ElasticsearchService:
    """
    Service layer for the Elasticsearch indexing and search pipeline.

    Args:
        repository:   Concrete ``ElasticsearchRepository`` instance.
        metadata_dir: Path to the metadata directory (contains /chunks/).
    """

    def __init__(
        self,
        repository: ElasticsearchRepository,
        metadata_dir: Path,
    ) -> None:
        self._repo = repository
        self._metadata_dir = metadata_dir
        self._chunks_dir = metadata_dir / "chunks"

    # ── Initialisation ─────────────────────────────────────────────────────────

    def ensure_index(self) -> bool:
        """
        Create the Elasticsearch index if it does not exist.

        Should be called once on application startup before any indexing.

        Returns:
            True if the index was created.
            False if it already existed.
        """
        return self._repo.create_index_if_not_exists()

    # ── Chunk Loading ──────────────────────────────────────────────────────────

    def load_chunks_for_document(self, document_id: str) -> List[DocumentChunk]:
        """
        Load all chunks for a document from its JSON file.

        Args:
            document_id: UUID of the document (filename prefix).

        Returns:
            List of ``DocumentChunk`` domain objects.

        Raises:
            FileNotFoundError: If the chunk file does not exist.
            IOError:           If the file cannot be parsed.
        """
        json_path = self._chunks_dir / f"{document_id}_chunks.json"
        if not json_path.exists():
            raise FileNotFoundError(
                f"Chunk file not found for document '{document_id}' at '{json_path}'."
            )

        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        raw_chunks: List[Dict[str, Any]] = (
            data["chunks"] if isinstance(data, dict) and "chunks" in data else data
        )

        chunks: List[DocumentChunk] = []
        for c in raw_chunks:
            page_val = c.get("page_number") or c.get("page")
            chunks.append(
                DocumentChunk(
                    chunk_id=c["chunk_id"],
                    document_id=c["document_id"],
                    document_name=c.get("document_name", ""),
                    category=c.get("category", ""),
                    page_number=int(page_val) if page_val is not None else 1,
                    chunk_index=c.get("chunk_index", 0),
                    text=c.get("chunk_text", c.get("text", "")),
                    char_count=c.get("char_count", 0),
                    source=c.get("source", ""),
                    metadata=c.get("metadata", {}),
                )
            )
        return chunks

    # ── Indexing ───────────────────────────────────────────────────────────────

    async def index_document(self, document_id: str) -> Dict[str, int]:
        """
        Load and index all chunks for a single document.

        Args:
            document_id: UUID of the document to index.

        Returns:
            Dict with ``total``, ``indexed``, ``failed`` counts.
        """
        t0 = time.perf_counter()
        elastic_log.info(
            "Indexing document | document_id={did}", did=document_id
        )

        chunks = self.load_chunks_for_document(document_id)
        elastic_log.info(
            "Loaded {n} chunks for document | document_id={did}",
            n=len(chunks),
            did=document_id,
        )

        await self._repo.index_chunks(chunks)

        elapsed = time.perf_counter() - t0
        elastic_log.info(
            "Document indexed | document_id={did} | chunks={n} | time={t:.2f}s",
            did=document_id,
            n=len(chunks),
            t=elapsed,
        )
        return {"total": len(chunks), "indexed": len(chunks), "failed": 0}

    def save_statistics(self, stats: ElasticsearchStatistics) -> Path:
        """
        Persist run statistics to ``metadata/elasticsearch_statistics.json``.

        Args:
            stats: ``ElasticsearchStatistics`` dataclass instance.

        Returns:
            Path to the written file.
        """
        stats_path = self._metadata_dir / "elasticsearch_statistics.json"
        payload: Dict[str, Any] = {
            "index_name": stats.index_name,
            "Total Chunks": stats.total_chunks,
            "Indexed Chunks": stats.indexed_chunks,
            "Failed Chunks": stats.failed_chunks,
            "Total Duration (s)": round(stats.total_duration_s, 2),
            "Average Chunk Time (ms)": round(stats.avg_chunk_time_ms, 4),
            "Processed At": stats.processed_at.isoformat(),
        }
        with open(stats_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        elastic_log.info(
            "Statistics saved | path={path}", path=str(stats_path)
        )
        return stats_path

    # ── Search ─────────────────────────────────────────────────────────────────

    async def keyword_search(
        self,
        query: str,
        top_k: int = 10,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None,
        fuzzy: bool = False,
    ) -> List[RetrievedChunk]:
        """
        Execute a BM25 keyword search and return ranked results.

        Args:
            query:           Full-text search query.
            top_k:           Maximum number of results.
            category_filter: Optional category filter.
            document_filter: Optional document_id filter.
            fuzzy:           Enable fuzzy matching for typo tolerance.

        Returns:
            List of ``RetrievedChunk`` ordered by BM25 score.
        """
        return await self._repo.search(
            query=query,
            top_k=top_k,
            category_filter=category_filter,
            document_filter=document_filter,
            fuzzy=fuzzy,
        )

    # ── Health ─────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if Elasticsearch is reachable."""
        return await self._repo.health_check()

    def get_index_stats(self) -> Dict[str, Any]:
        """Return document count and store size for the index."""
        return self._repo.get_index_stats()
