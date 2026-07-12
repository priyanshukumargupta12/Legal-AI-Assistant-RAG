"""
models/document.py
==================
Domain entity dataclasses for document, page, chunk, and citation.

PURPOSE:
    Pure Python dataclasses representing core business objects.
    These are the innermost domain objects — no framework imports,
    no database dependencies, no external library dependencies.

DESIGN:
    - Python dataclasses with type hints throughout
    - Frozen where immutable after creation (chunk_id, document_id)
    - __post_init__ used for derived field computation
    - All string fields stripped of whitespace on creation

SOLID: Each dataclass has exactly one responsibility (one entity).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DocumentMetadata:
    """
    Metadata extracted during dataset scanning for a single PDF file.

    Produced by DatasetScanner and DatasetService.
    Stored in documents.csv and documents.xlsx.

    Attributes:
        document_id:     Unique UUID for this document.
        file_name:       Original filename (e.g., "TaxCutsJobsAct.pdf").
        category:        Dataset category (Acts, CourtJudgement, Tax, Legal_opinion).
        file_path:       Absolute path to the PDF file.
        file_size_bytes: File size in bytes.
        page_count:      Number of pages extracted by PyMuPDF.
        md5_hash:        MD5 checksum for duplicate detection.
        status:          One of: "valid", "invalid", "duplicate".
        ingested_at:     Timestamp when the document was first scanned.
    """

    document_id: str
    file_name: str
    category: str
    file_path: str
    file_size_bytes: int
    page_count: int
    md5_hash: str
    status: str  # "valid" | "invalid" | "duplicate"
    ingested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class PageContent:
    """
    Raw text extracted from a single PDF page.

    Produced by PDFParser. Immutable after creation.

    Attributes:
        page_number: 1-based page number (PyMuPDF uses 0-based; we convert).
        text:        Raw extracted text from this page.
    """

    page_number: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    """
    Complete parsed representation of a PDF document.

    Produced by PDFParser. Contains all pages with their text content.
    Passed to ChunkBuilder for splitting.

    Attributes:
        document_id:   Unique UUID matching DocumentMetadata.document_id.
        file_name:     Original PDF filename.
        category:      Document category.
        pages:         Ordered list of PageContent objects (non-empty pages only).
        total_pages:   Total page count from the PDF (including empty pages).
    """

    document_id: str
    file_name: str
    category: str
    pages: tuple[PageContent, ...]
    total_pages: int


@dataclass(frozen=True)
class DocumentChunk:
    """
    A single text chunk extracted from a PDF document.

    Produced by ChunkBuilder. This is the fundamental unit stored in
    both Qdrant (as a vector) and Elasticsearch (as a document).

    Attributes:
        chunk_id:      Deterministic UUID5 based on document_id + chunk_index.
        document_id:   Parent document UUID.
        document_name: Parent document filename (for display in citations).
        category:      Document category.
        page_number:   Source page number (1-based).
        chunk_index:   Position of this chunk within the document (0-based).
        text:          Raw chunk text content.
        char_count:    Length of text in characters.
    """

    chunk_id: str
    document_id: str
    document_name: str
    category: str
    page_number: int
    chunk_index: int
    text: str
    char_count: int
    source: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Citation:
    """
    A source reference included in every query response.

    Produced by QueryService after hybrid retrieval and LLM generation.
    Displayed to the user alongside the answer.

    Attributes:
        document_name:    Source PDF filename.
        page_number:      Source page number (1-based).
        category:         Document category.
        excerpt:          Short text snippet from the source chunk (max 300 chars).
        rrf_score:        Reciprocal Rank Fusion score for this result.
        rank:             Final rank position (1–5).
    """

    document_name: str
    page_number: int
    category: str
    excerpt: str
    rrf_score: float
    rank: int


@dataclass
class RetrievedChunk:
    """
    A chunk returned by either the vector store or keyword store after search.

    Produced by QdrantRepository.search() or ElasticsearchRepository.search().
    Consumed by RRFRanker for merging and ranking.

    Attributes:
        chunk_id:      Unique chunk identifier (used for deduplication in RRF).
        document_id:   Parent document UUID.
        document_name: Source PDF filename.
        category:      Document category.
        page_number:   Source page number (1-based).
        chunk_index:   Position within document.
        text:          Chunk text content.
        score:         Raw retrieval score (cosine for vector, BM25 for keyword).
        rank:          Rank position within its retrieval source (1-indexed).
        source:        Which retriever produced this: "vector" or "keyword".
        rrf_score:     RRF score (set after merging, default 0.0).
    """

    chunk_id: str
    document_id: str
    document_name: str
    category: str
    page_number: int
    chunk_index: int
    text: str
    score: float
    rank: int
    source: str  # "vector" | "keyword"
    rrf_score: float = 0.0


@dataclass
class DatasetStatistics:
    """
    Aggregate statistics computed during a dataset scan.

    Produced by DatasetScanner and returned by DatasetService.
    Displayed on the frontend Dashboard.

    Attributes:
        total_pdfs:          Total PDF files discovered.
        valid_count:         PDFs successfully parsed.
        invalid_count:       PDFs that could not be opened.
        duplicate_count:     PDFs with duplicate MD5 hashes.
        acts_count:          Count of Acts category documents.
        court_count:         Count of CourtJudgement category documents.
        tax_count:           Count of Tax category documents.
        legal_opinion_count: Count of Legal_opinion category documents.
        avg_pages:           Average page count across valid documents.
        total_chunks:        Total chunks after ingestion (0 if not ingested).
        scanned_at:          Timestamp of the scan.
    """

    total_pdfs: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    acts_count: int
    court_count: int
    tax_count: int
    legal_opinion_count: int
    avg_pages: float
    total_chunks: int
    scanned_at: datetime = field(default_factory=datetime.utcnow)
