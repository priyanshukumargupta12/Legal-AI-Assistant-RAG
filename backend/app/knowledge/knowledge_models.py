"""
app/knowledge/knowledge_models.py
====================================
Pure Python domain models for the Open Knowledge Format (OKF) Standardization Module.

PURPOSE:
    Defines all domain entities produced by the OKF standardization pipeline.
    These models are framework-agnostic — only stdlib dataclasses and enums —
    making them reusable across any downstream system (Embeddings, Graph RAG, LLM).

WHY OKF IS REQUIRED:
======================
Without OKF standardization, every downstream system must re-implement its own
extraction of entities, keywords, legal sections, and references from raw text.
This leads to:
    - Duplicate extraction logic across Graph RAG, Evaluation, and LLM prompt builders.
    - Inconsistent results because each system uses different regex patterns.
    - No reusability across systems that consume the same legal data.
    - LLM prompts that contain only raw text, missing structured legal context.

OKF solves this by extracting once at standardization time:
    → Named Entities, Keywords, Legal Sections, References, Relationships

WHY OKF IMPROVES HYBRID RAG:
==============================
Hybrid RAG depends on two retrieval signals: vector similarity and BM25 keyword match.
OKF improves both:
    - VECTOR QUALITY:   Embeddings that include entity names and section refs score
                        more precisely against legal queries.
    - BM25 PRECISION:   Structured keyword fields give Elasticsearch richer term signals.
    - PROMPT ENRICHMENT: The LLM prompt builder can inject structured OKF metadata
                         (e.g., "This chunk cites IRC § 162") without re-parsing.

WHY GRAPH RAG USES STANDARDIZED KNOWLEDGE:
============================================
Graph RAG builds edges by detecting legal references between documents.
Without OKF, Graph RAG must scan every chunk from scratch on every build.
With OKF:
    - The "references" field contains pre-detected cross-document citation strings.
    - The "relationships" field contains pre-typed edge annotations (CITES, EXPLAINS).
    - Graph build time drops significantly; accuracy improves from consistent extraction.
    - Node summaries use OKF "top_keywords" for rich, interoperable node labels.

DESIGN:
    - EntityType enum covers all legal domain entity classes.
    - NamedEntity is immutable (frozen dataclass).
    - KnowledgeRelation carries typed, scored edge annotations.
    - KnowledgeChunk is the per-chunk OKF unit — the atomic knowledge object.
    - KnowledgeDocument aggregates all KnowledgeChunk signals for a single PDF.
    - KnowledgeBuildResult carries build statistics for API responses.

SOLID: Each dataclass has exactly one responsibility.
DRY:   All entity/relationship types defined here; never duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# ENUMERATIONS
# =============================================================================

class EntityType(str, Enum):
    """
    Enumeration of all named entity types detected in legal document text.

    Using str mixin allows EntityType values to be used directly in JSON output
    without additional serialization logic.

    Entity type rationale:
        PERSON      — Attorney, judge, petitioner, respondent names.
        ORG         — IRS, SEC, DOJ, agencies, corporations.
        COURT       — Tax Court, Circuit Court, District Court references.
        LAW         — IRC section references (IRC § 162, 26 U.S.C. § 409A).
        ACT         — Named statutory acts (Employee Retirement Income Security Act).
        SECTION     — Generic section references (Section 12, § 523(a)).
        PUBLICATION — IRS Publication references (Pub. 550, Publication 590-A).
        CFR         — Code of Federal Regulations references (26 CFR 1.401).
        MONEY       — Dollar amounts ($5,000, $1.2 million).
        DATE        — Legal dates (January 1, 2024; November 3, 2025).
        UNKNOWN     — Fallback for unclassified entities.
    """
    PERSON = "PERSON"
    ORG = "ORG"
    COURT = "COURT"
    LAW = "LAW"
    ACT = "ACT"
    SECTION = "SECTION"
    PUBLICATION = "PUBLICATION"
    CFR = "CFR"
    MONEY = "MONEY"
    DATE = "DATE"
    UNKNOWN = "UNKNOWN"


# =============================================================================
# NAMED ENTITY
# =============================================================================

@dataclass(frozen=True)
class NamedEntity:
    """
    A named entity detected in a chunk's text.

    Immutable (frozen=True) because entities are extracted once and should not
    be modified after extraction.

    Attributes:
        text:        The raw matched string (e.g., "IRC § 162", "IRS").
        entity_type: Semantic classification of the entity (EntityType enum).
        confidence:  Pattern match confidence score (0.0–1.0).
                     Higher values indicate stronger pattern matches.
    """

    text: str
    entity_type: EntityType
    confidence: float

    def to_dict(self) -> Dict:
        """Serialize NamedEntity to a JSON-serializable dictionary."""
        return {
            "text": self.text,
            "entity_type": self.entity_type.value,
            "confidence": round(self.confidence, 4),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "NamedEntity":
        """Deserialize a NamedEntity from a JSON dictionary."""
        return cls(
            text=data["text"],
            entity_type=EntityType(data.get("entity_type", "UNKNOWN")),
            confidence=float(data.get("confidence", 1.0)),
        )


# =============================================================================
# KNOWLEDGE RELATION
# =============================================================================

@dataclass(frozen=True)
class KnowledgeRelation:
    """
    A typed, scored relationship annotation extracted from a chunk.

    KnowledgeRelation makes each chunk "Graph RAG ready" without requiring
    re-scanning at graph build time. The relation_type maps directly to
    GraphEdge.EdgeType used by the Graph RAG module.

    Attributes:
        relation_type: Semantic type of the relationship (e.g., "CITES", "EXPLAINS").
                       Maps 1-to-1 with EdgeType values in the Graph RAG module.
        target_ref:    The matched text fragment that triggered this relation
                       (e.g., "IRC § 162", "Publication 550").
        confidence:    Pattern match confidence (0.0–1.0).
    """

    relation_type: str
    target_ref: str
    confidence: float

    def to_dict(self) -> Dict:
        """Serialize KnowledgeRelation to a JSON-serializable dictionary."""
        return {
            "relation_type": self.relation_type,
            "target_ref": self.target_ref,
            "confidence": round(self.confidence, 4),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeRelation":
        """Deserialize a KnowledgeRelation from a JSON dictionary."""
        return cls(
            relation_type=data.get("relation_type", "REFERS_TO"),
            target_ref=data.get("target_ref", ""),
            confidence=float(data.get("confidence", 0.5)),
        )


# =============================================================================
# KNOWLEDGE CHUNK  (per-chunk OKF object)
# =============================================================================

@dataclass
class KnowledgeChunk:
    """
    The atomic OKF unit — a standardized knowledge representation of a single chunk.

    KnowledgeChunk enriches a raw DocumentChunk with structured signals extracted
    by the NLP pipeline:
        - Named Entities  → people, laws, organizations, courts, publications
        - Keywords        → top-N high-signal domain terms
        - Legal Sections  → pre-extracted § / Section / IRC references
        - References      → cross-document citation strings
        - Relationships   → typed, scored edge annotations for Graph RAG

    Attributes:
        knowledge_id:     Globally unique OKF ID. Format: "okf_{chunk_id}".
        chunk_id:         Source chunk_id from the Chunking Module.
        document_id:      Parent document UUID.
        document_name:    Source PDF filename.
        category:         Legal category (Acts, CourtJudgement, Tax, Legal_opinion).
        page_number:      Source page number (1-based).
        chunk_index:      Zero-based position within the page.
        text:             Raw chunk text content.
        keywords:         Top-N extracted keyword strings.
        entities:         Detected NamedEntity objects.
        legal_sections:   Detected legal section reference strings (§, IRC, CFR).
        references:       Detected cross-document reference strings.
        relationships:    Typed KnowledgeRelation objects for Graph RAG edges.
        token_estimate:   Estimated LLM token count (char_count // 4).
        char_count:       Character length of the text field.
        source:           Source filename (same as document_name).
        created_at:       UTC timestamp of OKF standardization.
    """

    knowledge_id: str
    chunk_id: str
    document_id: str
    document_name: str
    category: str
    page_number: int
    chunk_index: int
    text: str
    keywords: List[str] = field(default_factory=list)
    entities: List[NamedEntity] = field(default_factory=list)
    legal_sections: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    relationships: List[KnowledgeRelation] = field(default_factory=list)
    token_estimate: int = 0
    char_count: int = 0
    source: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        """Serialize KnowledgeChunk to a JSON-serializable dictionary."""
        return {
            "knowledge_id": self.knowledge_id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "category": self.category,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "keywords": self.keywords,
            "entities": [e.to_dict() for e in self.entities],
            "legal_sections": self.legal_sections,
            "references": self.references,
            "relationships": [r.to_dict() for r in self.relationships],
            "token_estimate": self.token_estimate,
            "char_count": self.char_count,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeChunk":
        """Deserialize a KnowledgeChunk from a JSON dictionary."""
        return cls(
            knowledge_id=data["knowledge_id"],
            chunk_id=data["chunk_id"],
            document_id=data["document_id"],
            document_name=data["document_name"],
            category=data.get("category", ""),
            page_number=int(data.get("page_number", 0)),
            chunk_index=int(data.get("chunk_index", 0)),
            text=data.get("text", ""),
            keywords=data.get("keywords", []),
            entities=[NamedEntity.from_dict(e) for e in data.get("entities", [])],
            legal_sections=data.get("legal_sections", []),
            references=data.get("references", []),
            relationships=[KnowledgeRelation.from_dict(r) for r in data.get("relationships", [])],
            token_estimate=int(data.get("token_estimate", 0)),
            char_count=int(data.get("char_count", 0)),
            source=data.get("source", ""),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data else datetime.now(timezone.utc),
        )


# =============================================================================
# KNOWLEDGE DOCUMENT  (per-document OKF aggregate)
# =============================================================================

@dataclass
class KnowledgeDocument:
    """
    Document-level OKF object — aggregates all chunk-level knowledge signals
    for a single source PDF.

    KnowledgeDocument provides a complete, interoperable view of a legal document
    at the document granularity. Useful for:
        - Document-level vector embeddings (embed the top_keywords + summary)
        - Graph RAG node construction (entities, references, top_keywords)
        - LLM context injection at the document level
        - Cross-system document metadata exchange

    Attributes:
        document_id:          UUID of the source document.
        knowledge_id:         OKF document-level ID. Format: "okf_doc_{doc_id[:8]}".
        document_name:        Source PDF filename.
        category:             Legal category.
        source:               Same as document_name.
        total_pages:          Total pages in the source document.
        total_chunks:         Number of source chunks for this document.
        top_keywords:         Top-20 highest-frequency keywords across all chunks.
        all_entities:         Deduplicated named entities across all chunks.
        all_references:       Deduplicated cross-document reference strings.
        all_legal_sections:   Unique legal section references across all chunks.
        all_relationships:    Aggregated relationships across all chunks.
        chunk_ids:            All source chunk_ids belonging to this document.
        knowledge_chunk_ids:  All KnowledgeChunk.knowledge_id values for this document.
        created_at:           UTC timestamp of OKF document standardization.
    """

    document_id: str
    knowledge_id: str
    document_name: str
    category: str
    source: str
    total_pages: int = 0
    total_chunks: int = 0
    top_keywords: List[str] = field(default_factory=list)
    all_entities: List[NamedEntity] = field(default_factory=list)
    all_references: List[str] = field(default_factory=list)
    all_legal_sections: List[str] = field(default_factory=list)
    all_relationships: List[KnowledgeRelation] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    knowledge_chunk_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        """Serialize KnowledgeDocument to a JSON-serializable dictionary."""
        return {
            "document_id": self.document_id,
            "knowledge_id": self.knowledge_id,
            "document_name": self.document_name,
            "category": self.category,
            "source": self.source,
            "total_pages": self.total_pages,
            "total_chunks": self.total_chunks,
            "top_keywords": self.top_keywords,
            "all_entities": [e.to_dict() for e in self.all_entities],
            "all_references": self.all_references,
            "all_legal_sections": self.all_legal_sections,
            "all_relationships": [r.to_dict() for r in self.all_relationships],
            "chunk_ids": self.chunk_ids,
            "knowledge_chunk_ids": self.knowledge_chunk_ids,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeDocument":
        """Deserialize a KnowledgeDocument from a JSON dictionary."""
        return cls(
            document_id=data["document_id"],
            knowledge_id=data["knowledge_id"],
            document_name=data["document_name"],
            category=data.get("category", ""),
            source=data.get("source", data["document_name"]),
            total_pages=int(data.get("total_pages", 0)),
            total_chunks=int(data.get("total_chunks", 0)),
            top_keywords=data.get("top_keywords", []),
            all_entities=[NamedEntity.from_dict(e) for e in data.get("all_entities", [])],
            all_references=data.get("all_references", []),
            all_legal_sections=data.get("all_legal_sections", []),
            all_relationships=[KnowledgeRelation.from_dict(r) for r in data.get("all_relationships", [])],
            chunk_ids=data.get("chunk_ids", []),
            knowledge_chunk_ids=data.get("knowledge_chunk_ids", []),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data else datetime.now(timezone.utc),
        )


# =============================================================================
# BUILD RESULT
# =============================================================================

@dataclass
class KnowledgeBuildResult:
    """
    Statistics produced after a full OKF standardization build run.

    Returned by KnowledgeBuilder.build() and surfaced via the API response.

    Attributes:
        total_documents:        Number of documents standardized.
        total_knowledge_chunks: Total KnowledgeChunk objects produced.
        total_entities:         Total named entity occurrences detected.
        total_keywords:         Total unique keyword tokens extracted.
        total_references:       Total cross-document reference strings detected.
        total_legal_sections:   Total unique legal section references detected.
        total_relationships:    Total KnowledgeRelation annotations produced.
        chunks_processed:       Total source chunks scanned.
        build_time_ms:          Wall-clock build time in milliseconds.
        built_at:               UTC timestamp of this build run.
    """

    total_documents: int = 0
    total_knowledge_chunks: int = 0
    total_entities: int = 0
    total_keywords: int = 0
    total_references: int = 0
    total_legal_sections: int = 0
    total_relationships: int = 0
    chunks_processed: int = 0
    build_time_ms: float = 0.0
    built_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# STATS
# =============================================================================

@dataclass
class KnowledgeStats:
    """
    Lightweight statistics about the current OKF knowledge base state.

    Attributes:
        total_documents:        Number of KnowledgeDocument objects on disk.
        total_knowledge_chunks: Total KnowledgeChunk objects on disk.
        is_built:               Whether OKF knowledge files exist.
        last_built_at:          UTC timestamp of last build (None if never built).
        categories:             Document count per legal category.
    """

    total_documents: int = 0
    total_knowledge_chunks: int = 0
    is_built: bool = False
    last_built_at: Optional[datetime] = None
    categories: Dict[str, int] = field(default_factory=dict)
