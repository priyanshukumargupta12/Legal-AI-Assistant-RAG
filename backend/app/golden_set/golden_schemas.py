"""
app/golden_set/golden_schemas.py
==================================
Pydantic v2 API schemas for the Golden Set Management Module.

PURPOSE:
    Define the exact JSON shape of HTTP request bodies and response payloads
    for the /api/v1/golden/* endpoints.

    These schemas act as the serialization boundary between the internal
    domain models (golden_models.py) and the external API consumers
    (React frontend, API testing tools).

DESIGN:
    - All schemas inherit from pydantic.BaseModel (v2)
    - from_record() / from_report() / from_statistics() class methods
      convert domain models → schemas
    - No business logic — only structure and validation
    - model_config with from_attributes=True for dataclass compatibility

SOLID: Single Responsibility — only API data shapes for the golden set feature.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.golden_set.golden_models import (
    CategoryStats,
    FieldValidationError,
    GoldenRecord,
    GoldenRecordStatus,
    GoldenSetImportResult,
    GoldenSetStatistics,
    SourceMapping,
    ValidationReport,
)


# =============================================================================
# FIELD VALIDATION ERROR SCHEMA
# =============================================================================

class FieldValidationErrorSchema(BaseModel):
    """API representation of a single field validation error."""

    model_config = ConfigDict(from_attributes=True)

    row_number: int = Field(..., description="1-based row number in the source file.")
    field_name: str = Field(..., description="Column name that failed validation.")
    error_code: str = Field(..., description="Machine-readable error code.")
    error_message: str = Field(..., description="Human-readable error description.")
    raw_value: Optional[str] = Field(None, description="Raw value that caused the error.")

    @classmethod
    def from_error(cls, error: FieldValidationError) -> "FieldValidationErrorSchema":
        """Convert a domain FieldValidationError to an API schema."""
        return cls(
            row_number=error.row_number,
            field_name=error.field_name,
            error_code=error.error_code,
            error_message=error.error_message,
            raw_value=error.raw_value,
        )


# =============================================================================
# GOLDEN RECORD SCHEMA
# =============================================================================

class GoldenRecordSchema(BaseModel):
    """API representation of a single validated golden record."""

    model_config = ConfigDict(from_attributes=True)

    row_number: int = Field(..., description="Original row number in the source file.")
    query: str = Field(..., description="The legal question to be posed to the RAG system.")
    expected_answer: str = Field(..., description="The authoritative ground-truth answer.")
    source_document: str = Field(..., description="Reference PDF filename.")
    page_number: int = Field(..., ge=1, description="Page number in the source document.")
    category: str = Field(..., description="Legal category (Acts | CourtJudgement | Tax | Legal_opinion).")
    citation: Optional[str] = Field(None, description="Precise legal citation string.")
    difficulty: Optional[str] = Field(None, description="Difficulty level: easy | medium | hard.")
    tags: Optional[str] = Field(None, description="Comma-separated topic tags.")
    notes: Optional[str] = Field(None, description="Free-text annotator notes.")
    status: str = Field(..., description="Validation status: valid | invalid | duplicate | rejected.")
    query_length: int = Field(..., ge=0, description="Query length in characters.")
    answer_length: int = Field(..., ge=0, description="Expected answer length in characters.")
    validation_errors: List[FieldValidationErrorSchema] = Field(
        default_factory=list,
        description="Validation errors for INVALID records.",
    )

    @classmethod
    def from_record(cls, record: GoldenRecord) -> "GoldenRecordSchema":
        """Convert a domain GoldenRecord to an API schema."""
        return cls(
            row_number=record.row_number,
            query=record.query,
            expected_answer=record.expected_answer,
            source_document=record.source_document,
            page_number=record.page_number,
            category=record.category,
            citation=record.citation,
            difficulty=record.difficulty,
            tags=record.tags,
            notes=record.notes,
            status=record.status.value,
            query_length=record.query_length,
            answer_length=record.answer_length,
            validation_errors=[
                FieldValidationErrorSchema.from_error(e)
                for e in record.validation_errors
            ],
        )


# =============================================================================
# VALIDATION REPORT SCHEMA
# =============================================================================

class ValidationReportSchema(BaseModel):
    """API representation of the full validation report."""

    model_config = ConfigDict(from_attributes=True)

    total_rows: int = Field(..., description="Total rows read from the source file.")
    valid_count: int = Field(..., ge=0, description="Rows that passed all validation rules.")
    invalid_count: int = Field(..., ge=0, description="Rows with one or more violations.")
    duplicate_count: int = Field(..., ge=0, description="Rows with duplicate queries.")
    rejected_count: int = Field(..., ge=0, description="Empty rows that were skipped.")
    error_count: int = Field(..., ge=0, description="Total number of field-level errors.")
    success_rate: float = Field(..., ge=0.0, le=100.0, description="Percentage of valid rows.")
    source_file: str = Field(..., description="Name of the source file that was validated.")
    validated_at: datetime = Field(..., description="UTC timestamp of validation completion.")
    errors: List[FieldValidationErrorSchema] = Field(
        default_factory=list,
        description="All field-level validation errors.",
    )

    @classmethod
    def from_report(cls, report: ValidationReport) -> "ValidationReportSchema":
        """Convert a domain ValidationReport to an API schema."""
        return cls(
            total_rows=report.total_rows,
            valid_count=report.valid_count,
            invalid_count=report.invalid_count,
            duplicate_count=report.duplicate_count,
            rejected_count=report.rejected_count,
            error_count=report.error_count,
            success_rate=report.success_rate,
            source_file=report.source_file,
            validated_at=report.validated_at,
            errors=[FieldValidationErrorSchema.from_error(e) for e in report.errors],
        )


# =============================================================================
# CATEGORY STATS SCHEMA
# =============================================================================

class CategoryStatsSchema(BaseModel):
    """Per-category statistics for the statistics dashboard."""

    category: str = Field(..., description="Category name.")
    total: int = Field(..., ge=0, description="Total records in this category.")
    valid: int = Field(..., ge=0, description="Valid records.")
    invalid: int = Field(..., ge=0, description="Invalid records.")
    duplicate: int = Field(..., ge=0, description="Duplicate records.")
    avg_query_len: float = Field(..., ge=0.0, description="Average query length.")

    @classmethod
    def from_category_stats(cls, cs: CategoryStats) -> "CategoryStatsSchema":
        """Convert a domain CategoryStats to an API schema."""
        return cls(
            category=cs.category,
            total=cs.total,
            valid=cs.valid,
            invalid=cs.invalid,
            duplicate=cs.duplicate,
            avg_query_len=round(cs.avg_query_len, 1),
        )


# =============================================================================
# SOURCE MAPPING SCHEMA
# =============================================================================

class SourceMappingSchema(BaseModel):
    """Mapping of a golden source document to its dataset entry."""

    source_document: str = Field(..., description="Filename as it appears in the golden set.")
    document_id: Optional[str] = Field(None, description="UUID from documents.csv.")
    category: Optional[str] = Field(None, description="Dataset category.")
    page_count: Optional[int] = Field(None, description="Total pages in the PDF.")
    is_indexed: bool = Field(..., description="True if document exists in documents.csv.")

    @classmethod
    def from_mapping(cls, mapping: SourceMapping) -> "SourceMappingSchema":
        """Convert a domain SourceMapping to an API schema."""
        return cls(
            source_document=mapping.source_document,
            document_id=mapping.document_id,
            category=mapping.category,
            page_count=mapping.page_count,
            is_indexed=mapping.is_indexed,
        )


# =============================================================================
# GOLDEN SET STATISTICS SCHEMA
# =============================================================================

class GoldenSetStatisticsSchema(BaseModel):
    """API representation of the golden set statistics dashboard data."""

    model_config = ConfigDict(from_attributes=True)

    total_queries: int = Field(..., ge=0, description="Total records (all statuses).")
    valid_queries: int = Field(..., ge=0, description="Records with status=valid.")
    invalid_queries: int = Field(..., ge=0, description="Records with status=invalid.")
    duplicate_queries: int = Field(..., ge=0, description="Records with status=duplicate.")
    rejected_queries: int = Field(..., ge=0, description="Empty rows that were skipped.")
    valid_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of valid records.")
    category_distribution: Dict[str, int] = Field(
        ..., description="Category name → count of valid records."
    )
    category_stats: List[CategoryStatsSchema] = Field(
        default_factory=list,
        description="Detailed per-category breakdown.",
    )
    avg_query_length: float = Field(..., ge=0.0, description="Average query length (chars).")
    avg_answer_length: float = Field(..., ge=0.0, description="Average answer length (chars).")
    unique_source_docs: int = Field(..., ge=0, description="Number of distinct source documents.")
    source_file: str = Field(..., description="Filename that was imported.")
    computed_at: datetime = Field(..., description="UTC timestamp of statistics computation.")

    @classmethod
    def from_statistics(cls, stats: GoldenSetStatistics) -> "GoldenSetStatisticsSchema":
        """Convert a domain GoldenSetStatistics to an API schema."""
        return cls(
            total_queries=stats.total_queries,
            valid_queries=stats.valid_queries,
            invalid_queries=stats.invalid_queries,
            duplicate_queries=stats.duplicate_queries,
            rejected_queries=stats.rejected_queries,
            valid_percentage=stats.valid_percentage,
            category_distribution=stats.category_distribution,
            category_stats=[
                CategoryStatsSchema.from_category_stats(cs)
                for cs in stats.category_stats
            ],
            avg_query_length=round(stats.avg_query_length, 1),
            avg_answer_length=round(stats.avg_answer_length, 1),
            unique_source_docs=stats.unique_source_docs,
            source_file=stats.source_file,
            computed_at=stats.computed_at,
        )


# =============================================================================
# IMPORT RESULT SCHEMA
# =============================================================================

class ImportResultSchema(BaseModel):
    """API response returned after a golden set import operation."""

    model_config = ConfigDict(from_attributes=True)

    source_file_name: str = Field(..., description="Name of the imported file.")
    import_duration_s: float = Field(..., ge=0.0, description="Import duration in seconds.")
    statistics: GoldenSetStatisticsSchema = Field(..., description="Computed statistics.")
    validation_report: ValidationReportSchema = Field(..., description="Validation report.")
    source_mappings: List[SourceMappingSchema] = Field(
        default_factory=list,
        description="Source document → dataset mappings.",
    )
    message: str = Field(
        default="Golden set imported successfully.",
        description="Human-readable result message.",
    )

    @classmethod
    def from_import_result(cls, result: GoldenSetImportResult) -> "ImportResultSchema":
        """Convert a domain GoldenSetImportResult to an API schema."""
        valid_count = result.statistics.valid_queries
        total_count = result.statistics.total_queries
        message = (
            f"Import complete: {valid_count}/{total_count} records are valid. "
            f"See validation_report for details."
        )
        return cls(
            source_file_name=result.source_file_name,
            import_duration_s=round(result.import_duration_s, 3),
            statistics=GoldenSetStatisticsSchema.from_statistics(result.statistics),
            validation_report=ValidationReportSchema.from_report(result.validation_report),
            source_mappings=[
                SourceMappingSchema.from_mapping(m) for m in result.source_mappings
            ],
            message=message,
        )


# =============================================================================
# RECORDS LIST SCHEMA (PAGINATED)
# =============================================================================

class GoldenRecordsListSchema(BaseModel):
    """Paginated list of golden records."""

    total: int = Field(..., ge=0, description="Total records matching the filter.")
    valid_total: int = Field(..., ge=0, description="Total valid records in the full set.")
    page: int = Field(..., ge=1, description="Current page number (1-based).")
    page_size: int = Field(..., ge=1, description="Records per page.")
    total_pages: int = Field(..., ge=0, description="Total number of pages.")
    records: List[GoldenRecordSchema] = Field(..., description="Records on the current page.")
    category_filter: Optional[str] = Field(None, description="Applied category filter.")
    status_filter: Optional[str] = Field(None, description="Applied status filter.")


# =============================================================================
# EXPORT RESPONSE SCHEMA
# =============================================================================

class ExportResponseSchema(BaseModel):
    """Response for export endpoint confirming file availability."""

    file_name: str = Field(..., description="Name of the export file.")
    file_path: str = Field(..., description="Absolute path to the file on the server.")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes.")
    format: str = Field(..., description="Export format: csv | xlsx.")
    message: str = Field(
        default="Export file ready for download.",
        description="Human-readable confirmation.",
    )
