"""
app/dataset/dataset_models.py
==============================
Pure Python domain models for the Dataset Management Module.

PURPOSE:
    Defines all business entities used within the dataset module.
    These are the innermost domain objects — no Pydantic, no FastAPI,
    no external library imports. They contain only Python standard library.

    They are consumed by:
        - DatasetRepository (persistence)
        - DatasetService (business logic)
        - DatasetSchemas (API serialization via from_record())

ENTITIES:
    DocumentStatus    — enum: valid | invalid | corrupted | empty | duplicate
    DocumentRecord    — complete metadata for a single PDF file
    DatasetStatistics — aggregate statistics across all scanned documents
    ScanResult        — combined output of one scan operation

DESIGN:
    - Python dataclasses with type hints throughout
    - Frozen dataclasses where objects should be immutable after creation
    - `field(default=...)` used to avoid mutable default arguments
    - __post_init__ validates invariants without business logic

SOLID: Single Responsibility — only holds data; no methods perform logic.
DRY:   Single definition of each entity; referenced everywhere via import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# =============================================================================
# ENUMERATIONS
# =============================================================================

class DocumentStatus(str, Enum):
    """
    Lifecycle status of a discovered PDF document.

    Inherits from str so the value serializes naturally to JSON/CSV
    without needing .value accessor calls.

    Values:
        VALID:     PDF opened successfully; has at least one page.
        INVALID:   File exists but PyMuPDF cannot open it (not a valid PDF).
        CORRUPTED: File opened but internal structure is damaged (zero pages
                   or PDF read throws an error mid-way).
        EMPTY:     Valid PDF structure but contains zero extractable pages.
        DUPLICATE: Another file with identical SHA256 was already registered.
    """

    VALID = "valid"
    INVALID = "invalid"
    CORRUPTED = "corrupted"
    EMPTY = "empty"
    DUPLICATE = "duplicate"


# =============================================================================
# DOCUMENT RECORD
# =============================================================================

@dataclass
class DocumentRecord:
    """
    Complete metadata for a single discovered PDF file.

    Produced by DatasetService._process_pdf_file() for every PDF found
    during a directory scan. Stored as rows in documents.csv and
    documents.xlsx, and passed to the vector/keyword indexing pipeline.

    Attributes:
        document_id:       Deterministic UUID5 from SHA256 + relative path.
                           Stable across re-scans of the same file.
        file_name:         Original filename with extension (e.g., "TaxAct.pdf").
        title:             Display name derived from filename without extension.
        file_path:         Absolute path to the PDF on disk.
        relative_path:     Path relative to the dataset root (for portability).
        category:          One of Acts | CourtJudgement | Tax | Legal_opinion.
                           Derived automatically from the parent folder name.
        file_size_bytes:   File size in bytes from os.stat().
        page_count:        Number of pages reported by PyMuPDF.
                           0 for INVALID, CORRUPTED, or EMPTY documents.
        created_at:        File creation timestamp (platform-dependent).
        modified_at:       File last-modified timestamp from os.stat().
        checksum_sha256:   SHA256 hex digest of the raw file bytes.
                           Used for duplicate detection and integrity checks.
        status:            DocumentStatus enum value.
        is_duplicate_of:   document_id of the original file if DUPLICATE.
        error_message:     Human-readable error if status is not VALID.
    """

    document_id: str
    file_name: str
    title: str
    file_path: str
    relative_path: str
    category: str
    file_size_bytes: int
    page_count: int
    created_at: datetime
    modified_at: datetime
    checksum_sha256: str
    status: DocumentStatus
    is_duplicate_of: Optional[str] = field(default=None)
    error_message: Optional[str] = field(default=None)

    # ── Computed convenience properties ───────────────────────────────────────

    @property
    def file_size_mb(self) -> float:
        """File size in megabytes, rounded to 3 decimal places."""
        return round(self.file_size_bytes / (1024 * 1024), 3)

    @property
    def is_valid(self) -> bool:
        """True if the document is in VALID status."""
        return self.status == DocumentStatus.VALID

    @property
    def is_indexable(self) -> bool:
        """
        True if the document is suitable for ingestion into the RAG pipeline.
        Only VALID documents should be parsed, chunked, and indexed.
        """
        return self.status == DocumentStatus.VALID

    def __repr__(self) -> str:
        return (
            f"DocumentRecord(id={self.document_id[:8]}..., "
            f"file={self.file_name!r}, "
            f"category={self.category!r}, "
            f"pages={self.page_count}, "
            f"status={self.status.value!r})"
        )


# =============================================================================
# CATEGORY STATISTICS
# =============================================================================

@dataclass(frozen=True)
class CategoryStatistics:
    """
    Per-category counts within a dataset scan.

    Attributes:
        category:    Category name (e.g., "Acts").
        total:       Total PDFs found in this category folder.
        valid:       PDFs with status=VALID.
        invalid:     PDFs with status=INVALID or CORRUPTED or EMPTY.
        duplicate:   PDFs with status=DUPLICATE.
        total_pages: Sum of page counts across valid documents.
        total_size_bytes: Sum of file sizes across all documents.
    """

    category: str
    total: int
    valid: int
    invalid: int
    duplicate: int
    total_pages: int
    total_size_bytes: int

    @property
    def total_size_mb(self) -> float:
        """Total size of all category documents in megabytes."""
        return round(self.total_size_bytes / (1024 * 1024), 3)


# =============================================================================
# DATASET STATISTICS
# =============================================================================

@dataclass
class DatasetStatistics:
    """
    Aggregate statistics computed across all scanned PDF files.

    Produced by DatasetService._calculate_statistics() and returned as
    part of ScanResult. Exported to dataset_summary.json.

    Attributes:
        total_documents:      Total PDFs discovered across all category folders.
        valid_documents:      PDFs with status=VALID.
        invalid_documents:    PDFs with status=INVALID or CORRUPTED.
        empty_documents:      PDFs with status=EMPTY.
        duplicate_documents:  PDFs with status=DUPLICATE.
        avg_pages:            Mean page count across VALID documents.
        avg_file_size_bytes:  Mean file size across ALL documents.
        total_size_bytes:     Total bytes of all discovered files.
        category_counts:      Dict mapping category name → total PDF count.
        category_stats:       Detailed per-category breakdown.
        largest_pdf_name:     Filename of the largest PDF by page count.
        smallest_pdf_name:    Filename of the smallest VALID PDF by page count.
        scanned_at:           UTC timestamp when the scan was initiated.
        dataset_root:         Absolute path to the dataset root that was scanned.
    """

    total_documents: int
    valid_documents: int
    invalid_documents: int
    empty_documents: int
    duplicate_documents: int
    avg_pages: float
    avg_file_size_bytes: float
    total_size_bytes: int
    category_counts: dict[str, int]
    category_stats: list[CategoryStatistics]
    largest_pdf_name: Optional[str]
    smallest_pdf_name: Optional[str]
    scanned_at: datetime
    dataset_root: str

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def total_size_mb(self) -> float:
        """Total dataset size in megabytes."""
        return round(self.total_size_bytes / (1024 * 1024), 3)

    @property
    def total_size_gb(self) -> float:
        """Total dataset size in gigabytes."""
        return round(self.total_size_bytes / (1024 * 1024 * 1024), 4)

    @property
    def avg_file_size_mb(self) -> float:
        """Average file size in megabytes."""
        return round(self.avg_file_size_bytes / (1024 * 1024), 3)

    @property
    def valid_percentage(self) -> float:
        """Percentage of documents that are valid (0–100)."""
        if self.total_documents == 0:
            return 0.0
        return round(self.valid_documents / self.total_documents * 100, 1)

    def to_json_summary(self) -> dict:
        """
        Serialize to the canonical JSON summary format.

        Returns:
            dict: JSON-serializable summary matching the spec:
            {
                "total_documents": 100,
                "valid_documents": 95,
                ...
                "categories": {"Acts": 35, ...}
            }
        """
        return {
            "total_documents": self.total_documents,
            "valid_documents": self.valid_documents,
            "invalid_documents": self.invalid_documents,
            "empty_documents": self.empty_documents,
            "duplicate_documents": self.duplicate_documents,
            "categories": self.category_counts,
            "avg_pages": round(self.avg_pages, 2),
            "avg_file_size_mb": self.avg_file_size_mb,
            "total_size_mb": self.total_size_mb,
            "valid_percentage": self.valid_percentage,
            "largest_pdf": self.largest_pdf_name,
            "smallest_pdf": self.smallest_pdf_name,
            "dataset_root": self.dataset_root,
            "scanned_at": self.scanned_at.isoformat() + "Z",
        }


# =============================================================================
# SCAN RESULT
# =============================================================================

@dataclass
class ScanResult:
    """
    Complete output of a single dataset scan operation.

    Returned by DatasetService.scan_dataset() and consumed by:
        - DatasetRepository (to persist CSV, XLSX, JSON)
        - DatasetController (to format HTTP response)
        - Ingestion pipeline (to identify VALID documents for processing)

    Attributes:
        documents:   Complete list of DocumentRecord objects (all statuses).
        statistics:  Aggregate DatasetStatistics for this scan.
        scan_errors: List of (folder_path, error_message) for folders that
                     could not be opened (e.g., permission denied).
    """

    documents: list[DocumentRecord]
    statistics: DatasetStatistics
    scan_errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def valid_documents(self) -> list[DocumentRecord]:
        """Filter: only documents with VALID status."""
        return [doc for doc in self.documents if doc.status == DocumentStatus.VALID]

    @property
    def invalid_documents(self) -> list[DocumentRecord]:
        """Filter: documents with INVALID, CORRUPTED, or EMPTY status."""
        return [
            doc for doc in self.documents
            if doc.status in (DocumentStatus.INVALID, DocumentStatus.CORRUPTED, DocumentStatus.EMPTY)
        ]

    @property
    def duplicate_documents(self) -> list[DocumentRecord]:
        """Filter: only documents with DUPLICATE status."""
        return [doc for doc in self.documents if doc.status == DocumentStatus.DUPLICATE]

    def get_by_category(self, category: str) -> list[DocumentRecord]:
        """
        Return all documents belonging to a specific category.

        Args:
            category: Category name (e.g., "Acts").

        Returns:
            List of DocumentRecord objects for that category.
        """
        return [doc for doc in self.documents if doc.category == category]
