"""
app/knowledge/knowledge_service.py
=====================================
Orchestration service for the OKF Knowledge Module.

PURPOSE:
    Coordinates all OKF operations:
        1. Build (or reload) the knowledge base from chunk metadata
        2. Load an existing knowledge base from disk on startup
        3. Provide all query/access operations for knowledge objects
        4. Return knowledge base statistics

    KnowledgeService is the single entry point for all OKF operations.
    All HTTP controllers and DI factories use this class.

DESIGN:
    - Holds the live in-memory knowledge state (documents + chunks + index).
    - On startup, if knowledge files exist on disk, they are loaded automatically.
    - Knowledge base is rebuilt on explicit POST /knowledge/build.
    - All build operations delegate to KnowledgeBuilder.
    - All I/O delegates to KnowledgeRepository.

SOLID:
    Single Responsibility — orchestration only; no extraction or I/O logic.
    Dependency Inversion — depends on injected KnowledgeRepository.
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.knowledge.knowledge_builder import KnowledgeBuilder
from app.knowledge.knowledge_logger import knowledge_log
from app.knowledge.knowledge_models import (
    KnowledgeBuildResult,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeStats,
)
from app.knowledge.knowledge_repository import KnowledgeRepository


class KnowledgeService:
    """
    Primary orchestration service for the OKF Knowledge Module.

    Manages in-memory knowledge state and coordinates KnowledgeBuilder (build)
    and KnowledgeRepository (I/O) subsystems.

    Constructor Args:
        repository:        Injected KnowledgeRepository for persistence.
        top_n_keywords:    Max keywords per chunk for NLP extraction.
        doc_top_keywords:  Max keywords for document-level aggregate.
        max_entities:      Max named entities per chunk.
        min_relation_conf: Minimum confidence for relation inclusion.
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
        top_n_keywords: int = 15,
        doc_top_keywords: int = 20,
        max_entities: int = 30,
        min_relation_conf: float = 0.4,
    ) -> None:
        self._repo = repository
        self._top_n_keywords = top_n_keywords
        self._doc_top_keywords = doc_top_keywords
        self._max_entities = max_entities
        self._min_conf = min_relation_conf

        # ── Live in-memory state ───────────────────────────────────────────
        self._documents: List[KnowledgeDocument] = []
        self._chunks: List[KnowledgeChunk] = []

        # Indexes for O(1) lookups
        self._doc_index: Dict[str, KnowledgeDocument] = {}   # document_id → doc
        self._chunk_index: Dict[str, KnowledgeChunk] = {}    # knowledge_id → chunk
        self._doc_chunk_map: Dict[str, List[KnowledgeChunk]] = {}  # document_id → chunks

        self._last_build_result: Optional[KnowledgeBuildResult] = None

        # Try to load existing knowledge base from disk on init
        self._try_load_existing()

        knowledge_log.info(
            "KnowledgeService initialized | is_built={built} | docs={d} | chunks={c}",
            built=self.is_built,
            d=len(self._documents),
            c=len(self._chunks),
        )

    # =========================================================================
    # STATE
    # =========================================================================

    @property
    def is_built(self) -> bool:
        """Return True if knowledge base is loaded in memory."""
        return bool(self._documents)

    # =========================================================================
    # PUBLIC API — BUILD
    # =========================================================================

    def build(self, force_rebuild: bool = True) -> KnowledgeBuildResult:
        """
        Build (or reload) the OKF knowledge base.

        If force_rebuild=False and knowledge already exists, returns the cached result.

        Args:
            force_rebuild: If True, re-run full build even if already built.

        Returns:
            KnowledgeBuildResult with statistics.
        """
        if self.is_built and not force_rebuild:
            knowledge_log.info("Knowledge already built, force_rebuild=False — skipping")
            return self._last_build_result or self._make_stats_result()

        knowledge_log.info("Starting OKF build | force={force}", force=force_rebuild)

        builder = KnowledgeBuilder(
            repository=self._repo,
            top_n_keywords=self._top_n_keywords,
            doc_top_keywords=self._doc_top_keywords,
            max_entities=self._max_entities,
            min_relation_conf=self._min_conf,
        )

        result = builder.build()

        # Reload from disk into memory to populate indexes
        self._load_and_index(
            self._repo.load_knowledge_documents(),
            self._repo.load_knowledge_chunks(),
        )

        self._last_build_result = result
        return result

    # =========================================================================
    # PUBLIC API — QUERIES
    # =========================================================================

    def get_stats(self) -> KnowledgeStats:
        """Return current knowledge base statistics."""
        categories: Dict[str, int] = Counter(d.category for d in self._documents)

        last_built_at = None
        if self._last_build_result:
            last_built_at = self._last_build_result.built_at
        elif self._documents:
            last_built_at = self._documents[0].created_at

        return KnowledgeStats(
            total_documents=len(self._documents),
            total_knowledge_chunks=len(self._chunks),
            is_built=self.is_built,
            last_built_at=last_built_at,
            categories=dict(categories),
        )

    def get_all_documents(self) -> List[KnowledgeDocument]:
        """Return all KnowledgeDocument objects in memory."""
        return list(self._documents)

    def get_document_by_id(self, document_id: str) -> Optional[KnowledgeDocument]:
        """
        Retrieve a single KnowledgeDocument by its document_id.

        Args:
            document_id: UUID of the source document.

        Returns:
            KnowledgeDocument instance or None.
        """
        return self._doc_index.get(document_id)

    def get_chunks(self, doc_id: Optional[str] = None) -> List[KnowledgeChunk]:
        """
        Return all knowledge chunks, optionally filtered by document_id.

        Args:
            doc_id: Optional document_id filter.

        Returns:
            List of KnowledgeChunk objects.
        """
        if doc_id:
            return list(self._doc_chunk_map.get(doc_id, []))
        return list(self._chunks)

    def get_chunk_by_id(self, knowledge_id: str) -> Optional[KnowledgeChunk]:
        """
        Retrieve a single KnowledgeChunk by its knowledge_id.

        Args:
            knowledge_id: OKF knowledge_id (format: "okf_{chunk_id}").

        Returns:
            KnowledgeChunk instance or None.
        """
        return self._chunk_index.get(knowledge_id)

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _try_load_existing(self) -> None:
        """Attempt to load a persisted knowledge base from disk on initialization."""
        if not self._repo.knowledge_exists():
            knowledge_log.info("No persisted OKF knowledge found — will build on first request")
            return

        try:
            docs = self._repo.load_knowledge_documents()
            chunks = self._repo.load_knowledge_chunks()
            self._load_and_index(docs, chunks)
            knowledge_log.info(
                "Restored OKF knowledge base from disk | docs={d} | chunks={c}",
                d=len(docs),
                c=len(chunks),
            )
        except Exception as exc:  # noqa: BLE001
            knowledge_log.error(
                "Failed to load persisted knowledge base | error={e}", e=str(exc)
            )

    def _load_and_index(
        self,
        documents: List[KnowledgeDocument],
        chunks: List[KnowledgeChunk],
    ) -> None:
        """
        Load documents and chunks into memory and build lookup indexes.

        Args:
            documents: List of KnowledgeDocument objects.
            chunks:    List of KnowledgeChunk objects.
        """
        self._documents = documents
        self._chunks = chunks

        # Build O(1) indexes
        self._doc_index = {d.document_id: d for d in documents}
        self._chunk_index = {c.knowledge_id: c for c in chunks}

        # Build doc_id → chunks map
        self._doc_chunk_map = {}
        for chunk in chunks:
            if chunk.document_id not in self._doc_chunk_map:
                self._doc_chunk_map[chunk.document_id] = []
            self._doc_chunk_map[chunk.document_id].append(chunk)

    def _make_stats_result(self) -> KnowledgeBuildResult:
        """Create a KnowledgeBuildResult from current in-memory state (used if last result is None)."""
        return KnowledgeBuildResult(
            total_documents=len(self._documents),
            total_knowledge_chunks=len(self._chunks),
        )
