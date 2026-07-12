"""
app/golden_set/golden_models.py
================================
Pure Python domain models for the Golden Set Management Module.

PURPOSE:
    Defines all business entities used within the golden set module.
    These are the innermost domain objects — no Pydantic, no FastAPI,
    no external library imports. They contain only Python standard library.

    They are consumed by:
        - GoldenSetRepository (persistence)
        - GoldenSetService (business logic)
        - GoldenSchemas (API serialization)
        - GoldenExtensions (future pipeline adapters)

ENTITIES:
    GoldenRecordStatus   — enum: valid | invalid | duplicate | rejected
    GoldenSetUseCase     — enum: rag_benchmarking | retrieval_optimization |
                           prompt_optimization | llm_fine_tuning
    ExportFormat         — enum: csv | xlsx | json | jsonl | parquet
    DataSplit            — enum: train | validation | test | all
    GoldenRecord         — complete Q&A record (includes optional split / use_case_tags)
    FieldValidationError — single field-level validation error
    ValidationReport     — aggregated report of all validation errors
    GoldenSetStatistics  — aggregate statistics across all records
    CategoryStats        — per-category record distribution
    SourceMapping        — maps Source_Document to dataset metadata
    GoldenSetExportConfig — configuration object for use-case-specific exports
    GoldenSetImportResult — combined output of one import operation

DESIGN:
    - Python dataclasses with type hints throughout
    - Frozen dataclasses where objects should be immutable after creation
    - `field(default=...)` used to avoid mutable default arguments
    - __post_init__ validates invariants without business logic
    - Extension enums are ADDITIVE — never remove or rename existing values

EXTENSIBILITY:
    The module is designed as the data layer for four future use cases:

    1. RAG Benchmarking (current):
       Records are used to measure Precision@K, Recall@K, Faithfulness.

    2. Retrieval Optimization (future):
       Records provide (query, relevant_doc, relevant_page) triples for
       fine-tuning retrieval models (BGE, ColBERT, DPR).

    3. Prompt Optimization (future):
       Records provide (query, expected_answer) pairs for evaluating and
       optimizing system prompts via automatic prompt engineering.

    4. LLM Fine-Tuning (future):
       Records serialized as (instruction, input, output) triples in JSONL
       format for supervised fine-tuning of legal LLMs.

    Each use case will implement GoldenSetAdapter (see golden_extensions.py)
    and declare its required ExportFormat and DataSplit configuration via
    GoldenSetExportConfig.

SOLID: Single Responsibility — only holds data; no methods perform logic.
DRY:   Single definition of each entity; referenced everywhere via import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# ENUMERATIONS
# =============================================================================

class GoldenRecordStatus(str, Enum):
    """
    Validation status of a golden set record.

    Inherits from str so the value serializes naturally to JSON/CSV
    without needing .value accessor calls.

    Values:
        VALID:     Record passed all validation rules.
        INVALID:   Record has one or more field violations (missing/invalid).
        DUPLICATE: Another record with an identical query already exists.
        REJECTED:  Record is an empty row and was completely skipped.
    """

    VALID = "valid"
    INVALID = "invalid"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


class GoldenSetUseCase(str, Enum):
    """
    The downstream use case a golden set export is prepared for.

    Used by GoldenSetExportConfig and GoldenSetAdapter implementations
    to select the correct output format, field mapping, and split strategy.

    Values:
        RAG_BENCHMARKING:        Default. Measures RAG pipeline quality
                                 (Precision@K, Recall@K, Faithfulness).
                                 Required fields: query, expected_answer,
                                 source_document, page_number.

        RETRIEVAL_OPTIMIZATION:  Provides (query, relevant_doc, page) triples
                                 for re-ranking / embedding model fine-tuning.
                                 Required fields: query, source_document,
                                 page_number, category.

        PROMPT_OPTIMIZATION:     Provides (query, expected_answer) pairs for
                                 automatic prompt engineering / DSPy-style
                                 optimization.
                                 Required fields: query, expected_answer.

        LLM_FINE_TUNING:         Serializes records as (instruction, input,
                                 output) JSONL triples for supervised
                                 fine-tuning of legal language models.
                                 Required fields: all required fields.
                                 NOT IMPLEMENTED — architecture only.
    """

    RAG_BENCHMARKING = "rag_benchmarking"
    RETRIEVAL_OPTIMIZATION = "retrieval_optimization"
    PROMPT_OPTIMIZATION = "prompt_optimization"
    LLM_FINE_TUNING = "llm_fine_tuning"


class ExportFormat(str, Enum):
    """
    Output file format for a golden set export operation.

    Different downstream use cases require different formats:
        RAG Benchmarking:       csv | xlsx
        Retrieval Optimization: json | jsonl
        Prompt Optimization:    json | jsonl
        LLM Fine-Tuning:        jsonl | parquet (HuggingFace Datasets)

    Values:
        CSV:     Comma-separated values. Default human-readable format.
        XLSX:    Excel with status color coding. Best for manual review.
        JSON:    Full JSON array. Easy to parse, larger file size.
        JSONL:   JSON Lines. One record per line. Preferred for
                 streaming, HuggingFace Datasets, and fine-tuning.
        PARQUET: Columnar binary format. Efficient for large datasets
                 and Spark / HuggingFace Datasets workflows.
                 NOT IMPLEMENTED — architecture only.
    """

    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"


class DataSplit(str, Enum):
    """
    Train/validation/test split designation for a golden record.

    Assigned during export via a splitter strategy (e.g., random 80/10/10,
    category-stratified, or difficulty-stratified). Not assigned during import.

    Used by LLM fine-tuning and retrieval optimization pipelines that require
    separate train and evaluation sets.

    Values:
        TRAIN:      Used to train / fine-tune the model.
        VALIDATION: Used during training for early stopping / hyperparameter
                    search. Not seen by the model during evaluation.
        TEST:       Held-out set. Used only for final benchmark reporting.
        UNASSIGNED: Default. Record has not been assigned to any split yet.
    """

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    UNASSIGNED = "unassigned"


# =============================================================================
# FIELD VALIDATION ERROR
# =============================================================================

@dataclass(frozen=True)
class FieldValidationError:
    """
    A single validation error for one field of one golden record.

    Attributes:
        row_number:   1-based row index in the source file (header = row 1).
        field_name:   The column/field name that failed validation.
        error_code:   Machine-readable error code (e.g., "MISSING_QUERY").
        error_message: Human-readable description of the violation.
        raw_value:    The raw string value that caused the failure (may be None).
    """

    row_number: int
    field_name: str
    error_code: str
    error_message: str
    raw_value: Optional[str] = field(default=None)

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON export."""
        return {
            "row_number": self.row_number,
            "field_name": self.field_name,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "raw_value": self.raw_value,
        }


# =============================================================================
# GOLDEN RECORD
# =============================================================================

@dataclass
class GoldenRecord:
    """
    A single validated golden question-answer pair.

    This is the core domain entity of the Golden Set Management Module.
    Each record represents one expert-verified query with its ground truth
    answer, source document reference, and metadata.

    Required Fields (validated at import):
        query:           The legal question posed to the RAG system.
        expected_answer: The authoritative ground-truth answer.
        source_document: Filename of the reference PDF (e.g., "Title26_Vol2.pdf").
        page_number:     Page number in the source document containing the answer.
        category:        One of: Acts | CourtJudgement | Tax | Legal_opinion.

    Optional Fields:
        citation:    Precise legal citation (e.g., "Title 26 U.S.C. § 1.61").
        difficulty:  Subjective difficulty level: easy | medium | hard.
        tags:        Comma-separated topic tags.
        notes:       Free-text annotator notes.

    System Fields:
        row_number:  Original row index in the source file (1-based).
        status:      GoldenRecordStatus after validation.
        is_duplicate_of: query text of the duplicate if status=DUPLICATE.
        validation_errors: List of FieldValidationError for INVALID records.
    """

    # ── Required fields ───────────────────────────────────────────────────────
    query: str
    expected_answer: str
    source_document: str
    page_number: int
    category: str

    # ── Optional fields ───────────────────────────────────────────────────────
    citation: Optional[str] = field(default=None)
    difficulty: Optional[str] = field(default=None)
    tags: Optional[str] = field(default=None)
    notes: Optional[str] = field(default=None)

    # ── System fields ─────────────────────────────────────────────────────────
    row_number: int = field(default=0)
    status: GoldenRecordStatus = field(default=GoldenRecordStatus.VALID)
    is_duplicate_of: Optional[str] = field(default=None)
    validation_errors: List[FieldValidationError] = field(default_factory=list)

    # ── Extension fields (populated by pipeline adapters, not by import) ──────
    # These fields are intentionally NOT validated at import time.
    # They are populated by downstream pipeline adapters (see golden_extensions.py)
    # when the record is prepared for a specific use case.
    #
    # split:         Assigned by a DataSplitter before fine-tuning/retrieval export.
    # use_case_tags: Set by adapters to declare which use cases this record
    #                is suitable for (e.g., ["rag_benchmarking", "prompt_optimization"]).
    split: DataSplit = field(default=DataSplit.UNASSIGNED)
    use_case_tags: List[str] = field(default_factory=list)

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        """True if this record passed all validation checks."""
        return self.status == GoldenRecordStatus.VALID

    @property
    def query_length(self) -> int:
        """Length of the query string in characters."""
        return len(self.query)

    @property
    def answer_length(self) -> int:
        """Length of the expected answer string in characters."""
        return len(self.expected_answer)

    def __repr__(self) -> str:
        return (
            f"GoldenRecord(row={self.row_number}, "
            f"query={self.query[:40]!r}..., "
            f"source={self.source_document!r}, "
            f"page={self.page_number}, "
            f"status={self.status.value!r})"
        )


# =============================================================================
# VALIDATION REPORT
# =============================================================================

@dataclass
class ValidationReport:
    """
    Aggregated result of validating an entire golden set file.

    Produced by GoldenSetValidator.validate_records() and persisted by
    GoldenSetRepository. Returned to the frontend for display.

    Attributes:
        total_rows:     Total rows read from the source file (excluding header).
        valid_count:    Rows that passed all validation rules.
        invalid_count:  Rows with one or more field violations.
        duplicate_count: Rows with a duplicate query.
        rejected_count: Empty rows that were completely skipped.
        errors:         All FieldValidationError instances found during validation.
        validated_at:   UTC timestamp when validation completed.
        source_file:    Name of the source file that was validated.
    """

    total_rows: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    rejected_count: int
    errors: List[FieldValidationError]
    validated_at: datetime
    source_file: str

    @property
    def has_errors(self) -> bool:
        """True if any validation errors were found."""
        return len(self.errors) > 0

    @property
    def error_count(self) -> int:
        """Total number of field-level validation errors."""
        return len(self.errors)

    @property
    def errors_by_row(self) -> Dict[int, List[FieldValidationError]]:
        """Group errors by their row_number for display."""
        result: Dict[int, List[FieldValidationError]] = {}
        for err in self.errors:
            result.setdefault(err.row_number, []).append(err)
        return result

    @property
    def errors_by_field(self) -> Dict[str, List[FieldValidationError]]:
        """Group errors by their field_name for summary analysis."""
        result: Dict[str, List[FieldValidationError]] = {}
        for err in self.errors:
            result.setdefault(err.field_name, []).append(err)
        return result

    @property
    def success_rate(self) -> float:
        """Percentage of rows that passed validation (0–100)."""
        if self.total_rows == 0:
            return 0.0
        return round(self.valid_count / self.total_rows * 100, 2)

    def to_summary_dict(self) -> dict:
        """Serialize to a compact JSON-friendly summary dict."""
        return {
            "total_rows": self.total_rows,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "duplicate_count": self.duplicate_count,
            "rejected_count": self.rejected_count,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "source_file": self.source_file,
            "validated_at": self.validated_at.isoformat() + "Z",
            "errors": [e.to_dict() for e in self.errors],
        }


# =============================================================================
# CATEGORY STATISTICS
# =============================================================================

@dataclass(frozen=True)
class CategoryStats:
    """
    Per-category counts within a golden set.

    Attributes:
        category:      Category name (e.g., "Acts").
        total:         Total records in this category.
        valid:         Records with status=VALID.
        invalid:       Records with status=INVALID.
        duplicate:     Records with status=DUPLICATE.
        avg_query_len: Average query length (chars) for valid records.
    """

    category: str
    total: int
    valid: int
    invalid: int
    duplicate: int
    avg_query_len: float


# =============================================================================
# SOURCE DOCUMENT MAPPING
# =============================================================================

@dataclass(frozen=True)
class SourceMapping:
    """
    Maps a golden set Source_Document to its metadata in the dataset.

    Created by GoldenSetValidator when cross-referencing golden records
    against documents.csv. Used by the Evaluation Module to resolve which
    Qdrant/Elasticsearch chunks to compare against.

    Attributes:
        source_document:  Filename as it appears in the golden set.
        document_id:      UUID from documents.csv (None if not found).
        category:         Dataset category (None if not found).
        page_count:       Total pages in the PDF (None if not found).
        is_indexed:       True if the document exists in documents.csv.
    """

    source_document: str
    document_id: Optional[str]
    category: Optional[str]
    page_count: Optional[int]
    is_indexed: bool


# =============================================================================
# GOLDEN SET STATISTICS
# =============================================================================

@dataclass
class GoldenSetStatistics:
    """
    Aggregate statistics computed across all records in a golden set.

    Produced by StatisticsEngine.compute() and persisted to
    metadata/golden_set_statistics.json. Returned by the API for
    the frontend statistics dashboard.

    Attributes:
        total_queries:      Total records (all statuses).
        valid_queries:      Records with status=VALID.
        invalid_queries:    Records with status=INVALID.
        duplicate_queries:  Records with status=DUPLICATE.
        rejected_queries:   Empty rows that were skipped.
        category_distribution: Dict mapping category name → count of valid records.
        category_stats:     Detailed per-category breakdown.
        avg_query_length:   Mean query length in characters (valid records only).
        avg_answer_length:  Mean expected answer length (valid records only).
        unique_source_docs: Number of distinct Source_Document values.
        computed_at:        UTC timestamp when statistics were computed.
        source_file:        Filename that was imported.
        has_valid_records:  True if at least one valid record exists.
    """

    total_queries: int
    valid_queries: int
    invalid_queries: int
    duplicate_queries: int
    rejected_queries: int
    category_distribution: Dict[str, int]
    category_stats: List[CategoryStats]
    avg_query_length: float
    avg_answer_length: float
    unique_source_docs: int
    computed_at: datetime
    source_file: str

    @property
    def has_valid_records(self) -> bool:
        """True if at least one valid record exists."""
        return self.valid_queries > 0

    @property
    def valid_percentage(self) -> float:
        """Percentage of total records that are valid (0–100)."""
        if self.total_queries == 0:
            return 0.0
        return round(self.valid_queries / self.total_queries * 100, 2)

    def to_json_dict(self) -> dict:
        """Serialize to a JSON-friendly dict for persistence."""
        return {
            "total_queries": self.total_queries,
            "valid_queries": self.valid_queries,
            "invalid_queries": self.invalid_queries,
            "duplicate_queries": self.duplicate_queries,
            "rejected_queries": self.rejected_queries,
            "valid_percentage": self.valid_percentage,
            "category_distribution": self.category_distribution,
            "category_stats": [
                {
                    "category": cs.category,
                    "total": cs.total,
                    "valid": cs.valid,
                    "invalid": cs.invalid,
                    "duplicate": cs.duplicate,
                    "avg_query_len": round(cs.avg_query_len, 1),
                }
                for cs in self.category_stats
            ],
            "avg_query_length": round(self.avg_query_length, 1),
            "avg_answer_length": round(self.avg_answer_length, 1),
            "unique_source_docs": self.unique_source_docs,
            "source_file": self.source_file,
            "computed_at": self.computed_at.isoformat() + "Z",
        }


# =============================================================================
# IMPORT RESULT
# =============================================================================

@dataclass
class GoldenSetImportResult:
    """
    Combined output of a single golden set import operation.

    Returned by GoldenSetService.import_from_file() and consumed by:
        - GoldenSetRepository (persistence of CSV, XLSX, JSON)
        - GoldenSetController (formatting of HTTP response)
        - Evaluation Module (to resolve source→chunk mappings)

    Attributes:
        records:          All GoldenRecord objects (all statuses).
        validation_report: Full ValidationReport from the validator.
        statistics:       Computed GoldenSetStatistics.
        source_mappings:  List of SourceMapping for each unique source doc.
        source_file_name: Original filename that was imported.
        import_duration_s: Total time in seconds to complete the import.
    """

    records: List[GoldenRecord]
    validation_report: ValidationReport
    statistics: GoldenSetStatistics
    source_mappings: List[SourceMapping]
    source_file_name: str
    import_duration_s: float = field(default=0.0)

    @property
    def valid_records(self) -> List[GoldenRecord]:
        """Filter: only records with VALID status."""
        return [r for r in self.records if r.status == GoldenRecordStatus.VALID]

    @property
    def invalid_records(self) -> List[GoldenRecord]:
        """Filter: records with INVALID status."""
        return [r for r in self.records if r.status == GoldenRecordStatus.INVALID]

    @property
    def duplicate_records(self) -> List[GoldenRecord]:
        """Filter: records with DUPLICATE status."""
        return [r for r in self.records if r.status == GoldenRecordStatus.DUPLICATE]


# =============================================================================
# GOLDEN SET EXPORT CONFIG
# =============================================================================

@dataclass(frozen=True)
class GoldenSetExportConfig:
    """
    Configuration object that describes how a golden set should be exported
    for a specific downstream use case.

    This is the primary object exchanged between GoldenSetService and
    GoldenSetAdapter implementations. Each use-case adapter declares its
    own default GoldenSetExportConfig.

    NOT YET USED by any running adapter. This dataclass exists to define
    the interface contract for future adapters.

    Attributes:
        use_case:        The downstream use case this export targets.
        export_format:   The output file format (csv | xlsx | json | jsonl | parquet).
        include_invalid: Whether to include INVALID records in the export.
                         Default False — invalid records are typically excluded.
        include_duplicates: Whether to include DUPLICATE records in the export.
                         Default False for fine-tuning; True for benchmarking.
        split_ratios:    (train, validation, test) proportions as floats (must sum ≤ 1.0).
                         Only relevant when DataSplit is used.
                         Example: (0.8, 0.1, 0.1)
        split_strategy:  How to assign splits: "random" | "stratified_category" |
                         "stratified_difficulty".
                         Only relevant when split_ratios is provided.
        field_mapping:   Optional dict remapping canonical field names → output
                         column names. Used by adapters to reshape records for
                         specific frameworks (e.g., HuggingFace, OpenAI fine-tuning).
                         Example: {"query": "instruction", "expected_answer": "output"}
        metadata:        Free-form dict for adapter-specific configuration that
                         does not fit other fields.

    Usage (future example):
        config = GoldenSetExportConfig(
            use_case=GoldenSetUseCase.LLM_FINE_TUNING,
            export_format=ExportFormat.JSONL,
            include_duplicates=False,
            split_ratios=(0.8, 0.1, 0.1),
            split_strategy="stratified_category",
            field_mapping={"query": "instruction", "expected_answer": "output"},
        )
    """

    use_case: GoldenSetUseCase = field(default=GoldenSetUseCase.RAG_BENCHMARKING)
    export_format: ExportFormat = field(default=ExportFormat.CSV)
    include_invalid: bool = field(default=False)
    include_duplicates: bool = field(default=False)
    split_ratios: Optional[tuple] = field(default=None)  # (train, val, test)
    split_strategy: str = field(default="random")  # random | stratified_category | stratified_difficulty
    field_mapping: Optional[Dict[str, str]] = field(default=None)
    metadata: Optional[Dict[str, object]] = field(default=None)

    def __post_init__(self) -> None:
        """Validate split_ratios sum does not exceed 1.0."""
        if self.split_ratios is not None:
            if len(self.split_ratios) != 3:
                raise ValueError(
                    "split_ratios must be a 3-tuple (train, validation, test). "
                    f"Got length {len(self.split_ratios)}."
                )
            total = sum(self.split_ratios)
            if total > 1.0 + 1e-9:
                raise ValueError(
                    f"split_ratios must sum to ≤ 1.0, got {total:.4f}."
                )

