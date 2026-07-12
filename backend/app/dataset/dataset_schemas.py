"""
app/dataset/dataset_schemas.py
================================
Pydantic v2 API schemas for the Dataset Management Module.

PURPOSE:
    Define the exact JSON shape of HTTP request bodies and response payloads
    for the /api/v1/dataset/* endpoints.

    These schemas act as the serialization boundary between the internal
    domain models (dataset_models.py) and the external API consumers
    (React frontend, API testing tools).

DESIGN:
    - All schemas inherit from pydantic.BaseModel (v2)
    - from_record() class methods convert domain models → schemas
    - No business logic — only structure and validation
    - model_config with from_attributes=True for ORM/dataclass compatibility

SOLID: Single Responsibility — only API data shapes for the dataset feature.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.dataset.dataset_models import (
    CategoryStatistics,
    DatasetStatistics,
    DocumentRecord,
    DocumentStatus,
    ScanResult,
)


# =============================================================================
# DOCUMENT RECORD SCHEMA
# =============================================================================

class DocumentRecordSchema(BaseModel):
    """
    API representation of a single scanned PDF document.

    Returned as elements in DocumentListSchema and ScanResponseSchema.
    """

    document_id: str = Field(..., description="Deterministic UUID for this document.")
    file_name: str = Field(..., description="Original PDF filename.")
    title: str = Field(..., description="Display name (filename without extension).")
    file_path: str = Field(..., description="Absolute path to the PDF file.")
    relative_path: str = Field(..., description="Path relative to the dataset root.")
    category: str = Field(..., description="Document category (Acts | CourtJudgement | Tax | Legal_opinion).")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes.")
    file_size_mb: float = Field(..., ge=0.0, description="File size in megabytes.")
    page_count: int = Field(..., ge=0, description="Number of PDF pages (0 for invalid/empty).")
    created_at: datetime = Field(..., description="File creation timestamp (UTC).")
    modified_at: datetime = Field(..., description="File last-modified timestamp (UTC).")
    checksum_sha256: str = Field(..., description="SHA256 hex digest of the file bytes.")
    status: DocumentStatus = Field(..., description="Document status: valid | invalid | corrupted | empty | duplicate.")
    is_duplicate_of: Optional[str] = Field(default=None, description="document_id of the original if this is a duplicate.")
    error_message: Optional[str] = Field(default=None, description="Error description for non-valid documents.")

    model_config = {"from_attributes": True}

    @classmethod
    def from_record(cls, record: DocumentRecord) -> "DocumentRecordSchema":
        """
        Convert a DocumentRecord domain model to its API schema representation.

        Args:
            record: DocumentRecord from the dataset service.

        Returns:
            DocumentRecordSchema ready for JSON serialization.
        """
        return cls(
            document_id=record.document_id,
            file_name=record.file_name,
            title=record.title,
            file_path=record.file_path,
            relative_path=record.relative_path,
            category=record.category,
            file_size_bytes=record.file_size_bytes,
            file_size_mb=record.file_size_mb,
            page_count=record.page_count,
            created_at=record.created_at,
            modified_at=record.modified_at,
            checksum_sha256=record.checksum_sha256,
            status=record.status,
            is_duplicate_of=record.is_duplicate_of,
            error_message=record.error_message,
        )


# =============================================================================
# CATEGORY STATISTICS SCHEMA
# =============================================================================

class CategoryStatisticsSchema(BaseModel):
    """Per-category breakdown included in the scan statistics response."""

    category: str
    total: int = Field(..., ge=0)
    valid: int = Field(..., ge=0)
    invalid: int = Field(..., ge=0)
    duplicate: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
    total_size_bytes: int = Field(..., ge=0)
    total_size_mb: float = Field(..., ge=0.0)

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, stats: CategoryStatistics) -> "CategoryStatisticsSchema":
        """Convert CategoryStatistics domain model to schema."""
        return cls(
            category=stats.category,
            total=stats.total,
            valid=stats.valid,
            invalid=stats.invalid,
            duplicate=stats.duplicate,
            total_pages=stats.total_pages,
            total_size_bytes=stats.total_size_bytes,
            total_size_mb=stats.total_size_mb,
        )


# =============================================================================
# DATASET STATISTICS SCHEMA
# =============================================================================

class DatasetStatisticsSchema(BaseModel):
    """
    Aggregate statistics for the entire dataset, returned by the scan endpoint.
    """

    total_documents: int = Field(..., ge=0)
    valid_documents: int = Field(..., ge=0)
    invalid_documents: int = Field(..., ge=0)
    empty_documents: int = Field(..., ge=0)
    duplicate_documents: int = Field(..., ge=0)
    avg_pages: float = Field(..., ge=0.0, description="Mean page count across valid documents.")
    avg_file_size_bytes: float = Field(..., ge=0.0)
    avg_file_size_mb: float = Field(..., ge=0.0)
    total_size_bytes: int = Field(..., ge=0)
    total_size_mb: float = Field(..., ge=0.0)
    total_size_gb: float = Field(..., ge=0.0)
    valid_percentage: float = Field(..., ge=0.0, le=100.0)
    category_counts: dict[str, int] = Field(default_factory=dict)
    category_stats: List[CategoryStatisticsSchema] = Field(default_factory=list)
    largest_pdf: Optional[str] = None
    smallest_pdf: Optional[str] = None
    dataset_root: str
    scanned_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, stats: DatasetStatistics) -> "DatasetStatisticsSchema":
        """Convert DatasetStatistics domain model to schema."""
        return cls(
            total_documents=stats.total_documents,
            valid_documents=stats.valid_documents,
            invalid_documents=stats.invalid_documents,
            empty_documents=stats.empty_documents,
            duplicate_documents=stats.duplicate_documents,
            avg_pages=round(stats.avg_pages, 2),
            avg_file_size_bytes=round(stats.avg_file_size_bytes, 2),
            avg_file_size_mb=stats.avg_file_size_mb,
            total_size_bytes=stats.total_size_bytes,
            total_size_mb=stats.total_size_mb,
            total_size_gb=stats.total_size_gb,
            valid_percentage=stats.valid_percentage,
            category_counts=stats.category_counts,
            category_stats=[CategoryStatisticsSchema.from_model(cs) for cs in stats.category_stats],
            largest_pdf=stats.largest_pdf_name,
            smallest_pdf=stats.smallest_pdf_name,
            dataset_root=stats.dataset_root,
            scanned_at=stats.scanned_at,
        )


# =============================================================================
# SCAN RESPONSE SCHEMA
# =============================================================================

class ScanResponseSchema(BaseModel):
    """
    Complete response returned by POST /api/v1/dataset/scan.

    Contains the full statistics and the complete document list.
    """

    statistics: DatasetStatisticsSchema
    documents: List[DocumentRecordSchema]
    scan_errors: List[dict] = Field(
        default_factory=list,
        description="Folders that could not be scanned, with their errors.",
    )
    message: str = Field(..., description="Human-readable scan summary.")

    model_config = {"from_attributes": True}

    @classmethod
    def from_scan_result(cls, result: ScanResult) -> "ScanResponseSchema":
        """
        Convert a ScanResult domain object to the API response schema.

        Args:
            result: ScanResult from DatasetService.scan_dataset().

        Returns:
            ScanResponseSchema ready for FastAPI JSON serialization.
        """
        stats_schema = DatasetStatisticsSchema.from_model(result.statistics)
        doc_schemas = [DocumentRecordSchema.from_record(doc) for doc in result.documents]
        errors = [{"folder": folder, "error": error} for folder, error in result.scan_errors]

        message = (
            f"Scan complete: {result.statistics.total_documents} PDFs found | "
            f"{result.statistics.valid_documents} valid | "
            f"{result.statistics.invalid_documents} invalid | "
            f"{result.statistics.duplicate_documents} duplicate"
        )

        return cls(
            statistics=stats_schema,
            documents=doc_schemas,
            scan_errors=errors,
            message=message,
        )


# =============================================================================
# EXPORT RESPONSE SCHEMA
# =============================================================================

class ExportResponseSchema(BaseModel):
    """Response returned after generating CSV/XLSX/JSON export files."""

    csv_path: Optional[str] = Field(default=None, description="Absolute path to generated CSV file.")
    xlsx_path: Optional[str] = Field(default=None, description="Absolute path to generated XLSX file.")
    json_path: Optional[str] = Field(default=None, description="Absolute path to generated JSON summary file.")
    documents_exported: int = Field(..., ge=0, description="Number of documents written to files.")
    message: str


# =============================================================================
# DOCUMENT LIST SCHEMA (for GET /api/v1/dataset/documents)
# =============================================================================

class DocumentListSchema(BaseModel):
    """Paginated document list response."""

    total: int = Field(..., ge=0, description="Total documents in the registry.")
    valid: int = Field(..., ge=0)
    invalid: int = Field(..., ge=0)
    duplicate: int = Field(..., ge=0)
    documents: List[DocumentRecordSchema] = Field(default_factory=list)
    category_filter: Optional[str] = Field(default=None, description="Active category filter, if any.")
    status_filter: Optional[str] = Field(default=None, description="Active status filter, if any.")
