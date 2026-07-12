"""
app/chunking/chunk_models.py
=============================
Pure Python domain models for the Intelligent Chunking Module.

PURPOSE:
    Defines immutable, strongly-typed domain entities used throughout the
    chunking pipeline. These models contain only standard Python types —
    no framework dependencies — making them trivially testable and reusable
    across service, repository, and controller layers.

ENTITIES:
    DocumentChunk    — A single text split unit with all required metadata.
    ChunkStatistics  — Aggregate statistics computed over one document's chunks.
    GlobalChunkStats — Cross-document statistics for batch chunking runs.

DESIGN DECISIONS:
    - frozen=True on DocumentChunk prevents accidental mutation after creation
    - All metadata fields are typed explicitly (no bare dicts for domain fields)
    - token_estimate follows the rule: 1 token ≈ 4 characters (GPT standard)
    - chunk_size mirrors char_count for API readability

WHY CHUNK IDs MATTER:
    A deterministic chunk_id (e.g. "1808ca0c_PAGE015_CHUNK003") provides:
        1. Idempotent re-processing — same document always produces the same IDs
        2. Direct vector store key — Qdrant and Elasticsearch use it as a primary key
        3. Traceability — any chunk can be traced back to its source page and document

WHY PAGE METADATA MUST BE PRESERVED:
    Legal documents are often cited by page number ("see page 47, § 523(a)").
    Without preserving page_number in each chunk, the retrieval system cannot
    generate accurate citations back to the source document.

SOLID: Single Responsibility — only defines domain entities.
DRY:   All field semantics documented once here; never repeated in schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DocumentChunk:
    """
    Immutable domain entity representing a single text chunk produced by the
    Intelligent Chunking Module.

    A chunk is the atomic unit fed into the Embedding Pipeline. Every field
    is required so that downstream components (Qdrant, Elasticsearch, LLM)
    always have full context about where the text came from.

    Attributes:
        chunk_id:        Globally unique deterministic ID.
                         Format: <doc_prefix>_PAGE<PPP>_CHUNK<CCC>
                         Example: 1808ca0c_PAGE015_CHUNK003
        document_id:     UUID of the parent document (from DocumentRecord).
        document_name:   Original PDF filename (e.g. "Title11.pdf").
        category:        Legal document category (Acts, CourtJudgement, Tax, Legal_opinion).
        page_number:     1-based page number from which this chunk was extracted.
        chunk_index:     0-based index of this chunk within the page.
        text:            The actual split text content (cleaned).
        chunk_size:      Alias for char_count — target character length constraint.
        char_count:      Actual character length of the text field.
        token_estimate:  Estimated LLM token count (len(text) // 4).
        file_path:       Absolute file system path to the source PDF.
        source:          Name of the source file (same as document_name).
        metadata:        Preserved key-value metadata forwarded from the PDF Parser.
    """

    chunk_id: str
    document_id: str
    document_name: str
    category: str
    page_number: int
    chunk_index: int
    text: str
    chunk_size: int
    char_count: int
    token_estimate: int
    file_path: str
    source: str
    metadata: Dict[str, str]


@dataclass
class ChunkStatistics:
    """
    Aggregate statistics computed after splitting one document's pages into chunks.

    Used for logging, monitoring, and the API response payload.
    Mutable (not frozen) because it is assembled incrementally.

    Attributes:
        document_id:     UUID of the chunked document.
        document_name:   PDF filename for display.
        total_chunks:    Total number of valid chunks produced.
        avg_chunk_size:  Mean character length across all chunks.
        max_chunk_size:  Largest chunk in characters.
        min_chunk_size:  Smallest chunk in characters.
        chunks_per_page: Dict mapping page_number → number of chunks on that page.
        processed_at:    UTC timestamp of when chunking completed.
    """

    document_id: str
    document_name: str
    total_chunks: int
    avg_chunk_size: float
    max_chunk_size: int
    min_chunk_size: int
    chunks_per_page: Dict[int, int]
    processed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GlobalChunkStats:
    """
    Cross-document statistics produced by a batch chunking run (e.g. full dataset).

    Attributes:
        total_documents:      Number of documents processed in the run.
        total_chunks:         Total chunks produced across all documents.
        avg_chunk_size:       Grand average chunk size (chars) across all chunks.
        max_chunk_size:       Largest single chunk across all documents.
        min_chunk_size:       Smallest single chunk across all documents.
        chunks_per_document:  Dict mapping document_id → chunk count.
        failed_documents:     List of document_ids that failed during chunking.
        run_started_at:       UTC timestamp when the batch run began.
        run_completed_at:     UTC timestamp when the batch run ended.
    """

    total_documents: int
    total_chunks: int
    avg_chunk_size: float
    max_chunk_size: int
    min_chunk_size: int
    chunks_per_document: Dict[str, int]
    failed_documents: List[str] = field(default_factory=list)
    run_started_at: Optional[datetime] = None
    run_completed_at: Optional[datetime] = None
