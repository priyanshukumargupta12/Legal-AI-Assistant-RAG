"""
app/knowledge/knowledge_builder.py
=====================================
OKF standardization engine — converts raw chunks into Knowledge Objects.

PURPOSE:
    Orchestrates the full OKF standardization pipeline:
        1. Discover all chunk JSON files from metadata/chunks/
        2. For each chunk: extract entities, keywords, sections, references,
           and relationships using the NLP utility functions.
        3. Assemble a KnowledgeChunk for each source chunk.
        4. Aggregate all per-chunk signals into a KnowledgeDocument per PDF.
        5. Persist knowledge.json and knowledge_chunks.json via KnowledgeRepository.
        6. Return KnowledgeBuildResult with build statistics.

ALGORITHM — per chunk:
    text = chunk["text"]
    keywords         = extract_keywords(text, top_n)
    entities         = extract_entities(text, max_entities)
    legal_sections   = extract_legal_sections(text)
    references       = extract_references(text)
    relationships    = extract_relations(text)
    knowledge_chunk  = KnowledgeChunk(...)

ALGORITHM — per document (aggregation):
    top_keywords     = aggregate_keywords(all_chunk_keyword_lists, top_n=20)
    all_entities     = deduplicate_entities(all_chunk_entities)
    all_references   = deduplicate_strings(all_chunk_references)
    all_legal_sects  = deduplicate_strings(all_chunk_legal_sections)
    all_relations    = all_chunk_relations (aggregate, dedup by key)

DESIGN:
    - KnowledgeBuilder is stateless per build — re-instantiation is safe.
    - Chunk files are processed one at a time for memory efficiency.
    - KnowledgeRepository handles all I/O — builder has zero file access.
    - NLP utilities are pure functions — builder calls them directly.

SOLID:
    Single Responsibility — OKF standardization pipeline only.
    Open/Closed — new entity types added by extending knowledge_utils patterns.
    Dependency Inversion — depends on KnowledgeRepository abstraction.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from app.knowledge.knowledge_logger import knowledge_log
from app.knowledge.knowledge_models import (
    KnowledgeBuildResult,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeRelation,
    NamedEntity,
)
from app.knowledge.knowledge_repository import KnowledgeRepository
from app.knowledge.knowledge_utils import (
    aggregate_keywords,
    deduplicate_entities,
    deduplicate_strings,
    extract_entities,
    extract_keywords,
    extract_legal_sections,
    extract_references,
    extract_relations,
    generate_document_knowledge_id,
    generate_knowledge_id,
)


class KnowledgeBuilder:
    """
    Builds the OKF knowledge base from indexed chunk metadata files.

    Constructor Args:
        repository:        Injected KnowledgeRepository for all I/O.
        top_n_keywords:    Max keywords per chunk (default: 15).
        doc_top_keywords:  Max keywords per document aggregate (default: 20).
        max_entities:      Max named entities per chunk (default: 30).
        min_relation_conf: Minimum confidence for KnowledgeRelation inclusion.
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
        top_n_keywords: int = 15,
        doc_top_keywords: int = 20,
        max_entities: int = 30,
        min_relation_conf: float = 0.4,
    ) -> None:
        """
        Initialize the KnowledgeBuilder.

        Args:
            repository:        KnowledgeRepository for all I/O.
            top_n_keywords:    Max keywords extracted per chunk.
            doc_top_keywords:  Max keywords in document-level aggregate.
            max_entities:      Max named entities per chunk.
            min_relation_conf: Minimum confidence for relation inclusion.
        """
        self._repo = repository
        self._top_n_keywords = top_n_keywords
        self._doc_top_keywords = doc_top_keywords
        self._max_entities = max_entities
        self._min_conf = min_relation_conf

        knowledge_log.info(
            "KnowledgeBuilder initialized | keywords={k} | entities={e} | min_conf={mc}",
            k=top_n_keywords,
            e=max_entities,
            mc=min_relation_conf,
        )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def build(self) -> KnowledgeBuildResult:
        """
        Execute the full OKF standardization pipeline.

        PIPELINE:
            1. Discover and iterate chunk JSON files
            2. For each chunk: run NLP extraction
            3. Assemble KnowledgeChunk objects
            4. Aggregate per-document signals into KnowledgeDocument objects
            5. Persist via KnowledgeRepository
            6. Return build statistics

        Returns:
            KnowledgeBuildResult with statistics about the built knowledge base.
        """
        start_time = time.perf_counter()
        knowledge_log.info("OKF build started")

        all_knowledge_chunks: List[KnowledgeChunk] = []
        all_knowledge_docs: List[KnowledgeDocument] = []

        # Aggregate counters
        total_entities = 0
        total_keywords = 0
        total_references = 0
        total_sections = 0
        total_relations = 0
        chunks_processed = 0

        # Iterate documents one at a time (memory-efficient)
        for doc_name, raw_chunks in self._repo.iter_chunk_batches():
            if not raw_chunks:
                continue

            knowledge_log.info(
                "Processing document | doc={doc} | chunks={n}",
                doc=doc_name,
                n=len(raw_chunks),
            )

            # ── Per-document aggregation buffers ───────────────────────────
            doc_knowledge_chunks: List[KnowledgeChunk] = []
            doc_all_keywords: List[List[str]] = []
            doc_all_entities: List[NamedEntity] = []
            doc_all_references: List[str] = []
            doc_all_sections: List[str] = []
            doc_all_relations: List[KnowledgeRelation] = []
            doc_chunk_ids: List[str] = []
            doc_knowledge_ids: List[str] = []
            doc_id = ""
            doc_category = ""
            doc_max_page = 0

            # ── Process each chunk ─────────────────────────────────────────
            for raw_chunk in raw_chunks:
                chunk = self._process_chunk(raw_chunk)
                if chunk is None:
                    continue

                chunks_processed += 1
                doc_knowledge_chunks.append(chunk)

                # Update per-document buffers
                doc_all_keywords.append(chunk.keywords)
                doc_all_entities.extend(chunk.entities)
                doc_all_references.extend(chunk.references)
                doc_all_sections.extend(chunk.legal_sections)
                doc_all_relations.extend(chunk.relationships)
                doc_chunk_ids.append(chunk.chunk_id)
                doc_knowledge_ids.append(chunk.knowledge_id)

                # Update doc-level metadata from first valid chunk
                if not doc_id:
                    doc_id = chunk.document_id
                    doc_category = chunk.category
                if chunk.page_number > doc_max_page:
                    doc_max_page = chunk.page_number

                # Accumulate global counters
                total_entities += len(chunk.entities)
                total_keywords += len(chunk.keywords)
                total_references += len(chunk.references)
                total_sections += len(chunk.legal_sections)
                total_relations += len(chunk.relationships)

            # ── Assemble KnowledgeDocument ────────────────────────────────
            if doc_id and doc_knowledge_chunks:
                knowledge_doc = KnowledgeDocument(
                    document_id=doc_id,
                    knowledge_id=generate_document_knowledge_id(doc_id),
                    document_name=doc_name,
                    category=doc_category,
                    source=doc_name,
                    total_pages=doc_max_page,
                    total_chunks=len(doc_knowledge_chunks),
                    top_keywords=aggregate_keywords(doc_all_keywords, self._doc_top_keywords),
                    all_entities=deduplicate_entities(doc_all_entities),
                    all_references=deduplicate_strings(doc_all_references),
                    all_legal_sections=deduplicate_strings(doc_all_sections),
                    all_relationships=self._deduplicate_relations(doc_all_relations),
                    chunk_ids=doc_chunk_ids,
                    knowledge_chunk_ids=doc_knowledge_ids,
                )
                all_knowledge_docs.append(knowledge_doc)
                all_knowledge_chunks.extend(doc_knowledge_chunks)

                knowledge_log.info(
                    "Document OKF built | doc={doc} | knowledge_chunks={n} | entities={e} | keywords={k}",
                    doc=doc_name,
                    n=len(doc_knowledge_chunks),
                    e=len(knowledge_doc.all_entities),
                    k=len(knowledge_doc.top_keywords),
                )

        # ── Persist ────────────────────────────────────────────────────────
        self._repo.save_all(all_knowledge_docs, all_knowledge_chunks)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        result = KnowledgeBuildResult(
            total_documents=len(all_knowledge_docs),
            total_knowledge_chunks=len(all_knowledge_chunks),
            total_entities=total_entities,
            total_keywords=total_keywords,
            total_references=total_references,
            total_legal_sections=total_sections,
            total_relationships=total_relations,
            chunks_processed=chunks_processed,
            build_time_ms=round(elapsed_ms, 2),
        )

        knowledge_log.info(
            "OKF build complete | documents={d} | knowledge_chunks={c} | "
            "entities={e} | keywords={k} | references={r} | time={t:.1f}ms",
            d=result.total_documents,
            c=result.total_knowledge_chunks,
            e=result.total_entities,
            k=result.total_keywords,
            r=result.total_references,
            t=elapsed_ms,
        )

        return result

    # =========================================================================
    # PRIVATE — CHUNK PROCESSING
    # =========================================================================

    def _process_chunk(self, raw_chunk: Dict) -> Optional[KnowledgeChunk]:
        """
        Process a single raw chunk dictionary into a KnowledgeChunk.

        PIPELINE:
            1. Extract metadata fields from raw chunk dict.
            2. Validate that chunk_id and text are present.
            3. Run NLP extraction on chunk text.
            4. Assemble and return KnowledgeChunk.

        Args:
            raw_chunk: Raw dictionary loaded from a _chunks.json file.

        Returns:
            KnowledgeChunk instance, or None if chunk is invalid/empty.
        """
        chunk_id = raw_chunk.get("chunk_id", "")
        text = raw_chunk.get("text", raw_chunk.get("chunk_text", ""))

        if not chunk_id or not text or len(text.strip()) < 5:
            return None

        # Resolve fields — chunk JSON uses both "page" and "page_number"
        document_id = raw_chunk.get("document_id", "")
        document_name = raw_chunk.get("document_name", raw_chunk.get("source", ""))
        category = raw_chunk.get("category", "")
        page_number = int(raw_chunk.get("page_number", raw_chunk.get("page", 0)))
        chunk_index = int(raw_chunk.get("chunk_index", 0))
        token_estimate = int(raw_chunk.get("token_estimate", len(text) // 4))
        char_count = int(raw_chunk.get("char_count", len(text)))
        source = raw_chunk.get("source", document_name)

        # ── Run NLP extraction ────────────────────────────────────────────
        keywords = extract_keywords(text, top_n=self._top_n_keywords)
        entities = extract_entities(text, max_entities=self._max_entities)
        legal_sections = extract_legal_sections(text)
        references = extract_references(text)
        relationships = extract_relations(text, min_confidence=self._min_conf)

        return KnowledgeChunk(
            knowledge_id=generate_knowledge_id(chunk_id),
            chunk_id=chunk_id,
            document_id=document_id,
            document_name=document_name,
            category=category,
            page_number=page_number,
            chunk_index=chunk_index,
            text=text,
            keywords=keywords,
            entities=entities,
            legal_sections=legal_sections,
            references=references,
            relationships=relationships,
            token_estimate=token_estimate,
            char_count=char_count,
            source=source,
        )

    def _deduplicate_relations(
        self, relations: List[KnowledgeRelation]
    ) -> List[KnowledgeRelation]:
        """
        Deduplicate a list of KnowledgeRelation objects by (relation_type, target_ref) key.

        Keeps the instance with the highest confidence for each unique key.

        Args:
            relations: List of KnowledgeRelation objects (from all chunks).

        Returns:
            Deduplicated list sorted by confidence descending.
        """
        best: Dict[str, KnowledgeRelation] = {}
        for rel in relations:
            key = f"{rel.relation_type}::{rel.target_ref.lower()}"
            if key not in best or rel.confidence > best[key].confidence:
                best[key] = rel
        return sorted(best.values(), key=lambda r: r.confidence, reverse=True)
