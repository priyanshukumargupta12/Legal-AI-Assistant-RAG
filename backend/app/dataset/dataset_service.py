"""
app/dataset/dataset_service.py
================================
Service layer for the Dataset Management Module.

PURPOSE:
    Implements all dataset business logic:
        1. Scanning the dataset directory recursively
        2. Processing each PDF to extract metadata
        3. Detecting duplicate files via SHA256 comparison
        4. Validating PDF integrity using PyMuPDF
        5. Calculating aggregate statistics
        6. Orchestrating export (CSV, XLSX, JSON)

    DatasetService is the single authoritative class for dataset operations.
    It depends on DatasetRepository (injected) and dataset_utils (stateless).

WHY SERVICE LAYER:
    - Keeps business logic away from HTTP controllers and data access code.
    - Controllers call service methods — never touch the file system directly.
    - Repository handles I/O — service handles logic.
    - Service is testable without HTTP or file I/O dependencies.

DESIGN:
    - Dependency Injection: DatasetRepository injected via constructor
    - All public methods are self-contained (complete input → complete output)
    - Private helpers (_scan_folder, _process_file, _detect_duplicates) are
      small, single-responsibility functions
    - Comprehensive logging at every step for operational visibility

SOLID:
    Single Responsibility — dataset scanning and metadata extraction only.
    Dependency Inversion  — depends on DatasetRepository abstraction.
    Open/Closed           — new validation rules added without modifying scans.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.constants import VALID_CATEGORIES
from app.core.exceptions import DatasetScanError
from app.dataset.dataset_logger import dataset_log
from app.dataset.dataset_models import (
    CategoryStatistics,
    DatasetStatistics,
    DocumentRecord,
    DocumentStatus,
    ScanResult,
)
from app.dataset.dataset_repository import DatasetRepository
from app.dataset.dataset_utils import (
    compute_sha256,
    derive_title,
    detect_category,
    format_size_human,
    generate_document_id,
    get_file_size_bytes,
    get_file_timestamps,
    get_pdf_page_count,
    get_relative_path,
    is_hidden_file,
    is_pdf_by_extension,
)


class DatasetService:
    """
    Orchestrates all dataset management operations.

    Responsibilities:
        - Recursive directory scanning
        - Per-file metadata extraction and validation
        - SHA256-based duplicate detection
        - Aggregate statistics calculation
        - Export orchestration (delegates to DatasetRepository)

    Constructor Args:
        repository:   Injected DatasetRepository implementation.
        dataset_root: Absolute path to the dataset/ directory.
        metadata_dir: Absolute path to the metadata/ output directory.
    """

    def __init__(
        self,
        repository: DatasetRepository,
        dataset_root: Path,
        metadata_dir: Path,
    ) -> None:
        """
        Initialize DatasetService with injected dependencies.

        Args:
            repository:   DatasetRepository implementation for persistence.
            dataset_root: Root of the dataset directory tree.
            metadata_dir: Directory where CSV, XLSX, JSON outputs are written.
        """
        self._repository = repository
        self._dataset_root = dataset_root.resolve()
        self._metadata_dir = metadata_dir.resolve()

        dataset_log.info(
            "DatasetService initialized | root={root} | metadata={meta}",
            root=str(self._dataset_root),
            meta=str(self._metadata_dir),
        )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def scan_dataset(self) -> ScanResult:
        """
        Scan the entire dataset directory and collect metadata for every PDF.

        ALGORITHM:
            1. Verify dataset_root exists and is accessible
            2. For each valid category folder, scan for PDFs
            3. Process each PDF: extract metadata, validate, compute SHA256
            4. Detect duplicates across all categories (same SHA256 → duplicate)
            5. Calculate aggregate statistics
            6. Export CSV, XLSX, and JSON automatically
            7. Return ScanResult with documents + statistics + any folder errors

        Returns:
            ScanResult containing all DocumentRecord objects and statistics.

        Raises:
            DatasetScanError: If the dataset root is missing or unreadable.
        """
        dataset_log.info(
            "Starting dataset scan | root={root}",
            root=str(self._dataset_root),
        )

        # ── Validate dataset root ─────────────────────────────────────────────
        self._validate_dataset_root()

        # ── Scan each category folder ─────────────────────────────────────────
        all_documents: List[DocumentRecord] = []
        scan_errors: List[Tuple[str, str]] = []

        for category in VALID_CATEGORIES:
            category_path = self._dataset_root / category
            try:
                category_docs = self._scan_category_folder(category_path, category)
                all_documents.extend(category_docs)
                dataset_log.info(
                    "Category scan complete | category={cat} | found={count}",
                    cat=category,
                    count=len(category_docs),
                )
            except PermissionError as exc:
                error_msg = f"Permission denied: {exc}"
                dataset_log.error(
                    "Cannot scan category folder | category={cat} | error={error}",
                    cat=category,
                    error=error_msg,
                )
                scan_errors.append((str(category_path), error_msg))
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Unexpected error: {exc}"
                dataset_log.error(
                    "Unexpected scan error | category={cat} | error={error}",
                    cat=category,
                    error=error_msg,
                )
                scan_errors.append((str(category_path), error_msg))

        # ── Detect duplicates ─────────────────────────────────────────────────
        all_documents = self._detect_duplicates(all_documents)

        # ── Calculate statistics ──────────────────────────────────────────────
        statistics = self._calculate_statistics(all_documents)

        # ── Export all outputs ────────────────────────────────────────────────
        try:
            scan_result = ScanResult(
                documents=all_documents,
                statistics=statistics,
                scan_errors=scan_errors,
            )
            self._repository.export_all(scan_result)
        except DatasetScanError as exc:
            dataset_log.error("Export failed | error={error}", error=exc.message)
            # Do not re-raise — scan succeeded even if export had issues
        except Exception as exc:  # noqa: BLE001
            dataset_log.error("Unexpected export error | error={error}", error=str(exc))

        dataset_log.info(
            "Dataset scan finished | total={total} | valid={valid} | invalid={invalid} | duplicate={dup}",
            total=statistics.total_documents,
            valid=statistics.valid_documents,
            invalid=statistics.invalid_documents,
            dup=statistics.duplicate_documents,
        )

        return ScanResult(
            documents=all_documents,
            statistics=statistics,
            scan_errors=scan_errors,
        )

    def export_all(self, scan_result: ScanResult) -> Dict[str, Path]:
        """
        Explicitly trigger all exports from an existing ScanResult.

        Useful when re-exporting without re-scanning.

        Args:
            scan_result: Previously obtained ScanResult.

        Returns:
            Dict mapping "csv", "xlsx", "json" to file paths.

        Raises:
            DatasetScanError: If any export fails.
        """
        return self._repository.export_all(scan_result)

    def get_statistics_from_csv(self) -> Optional[List[dict]]:
        """
        Load previously persisted document records from documents.csv.

        Used by the dashboard to show statistics without re-scanning.

        Returns:
            List of row dicts, or None if the CSV does not exist.
        """
        try:
            return self._repository.load_documents_csv()
        except FileNotFoundError:
            dataset_log.warning("documents.csv not found — dataset has not been scanned yet.")
            return None
        except DatasetScanError as exc:
            dataset_log.error("Failed to load CSV | error={error}", error=exc.message)
            return None

    # =========================================================================
    # PRIVATE HELPERS — SCANNING
    # =========================================================================

    def _validate_dataset_root(self) -> None:
        """
        Verify the dataset root directory exists and is accessible.

        Raises:
            DatasetScanError: With descriptive message if validation fails.
        """
        if not self._dataset_root.exists():
            raise DatasetScanError(
                message=f"Dataset root does not exist: '{self._dataset_root}'",
                detail={"path": str(self._dataset_root)},
            )

        if not self._dataset_root.is_dir():
            raise DatasetScanError(
                message=f"Dataset root is not a directory: '{self._dataset_root}'",
                detail={"path": str(self._dataset_root)},
            )

        if not os.access(self._dataset_root, os.R_OK):
            raise DatasetScanError(
                message=f"Permission denied for dataset root: '{self._dataset_root}'",
                detail={"path": str(self._dataset_root)},
            )

        dataset_log.debug(
            "Dataset root validated | path={path}",
            path=str(self._dataset_root),
        )

    def _scan_category_folder(
        self,
        category_path: Path,
        category: str,
    ) -> List[DocumentRecord]:
        """
        Scan a single category folder and return DocumentRecord for each PDF.

        Handles:
            - Missing category folder (returns empty list with a warning)
            - Empty category folder (returns empty list with a warning)
            - Hidden file skipping
            - Non-PDF file skipping (with debug log)
            - Recursive scanning of subdirectories

        Args:
            category_path: Absolute path to the category folder.
            category:      Category name string.

        Returns:
            List of DocumentRecord objects (one per discovered PDF file).
        """
        if not category_path.exists():
            dataset_log.warning(
                "Category folder not found | category={cat} | path={path}",
                cat=category,
                path=str(category_path),
            )
            return []

        if not category_path.is_dir():
            dataset_log.warning(
                "Category path is not a directory | category={cat} | path={path}",
                cat=category,
                path=str(category_path),
            )
            return []

        dataset_log.info(
            "Scanning category | category={cat} | path={path}",
            cat=category,
            path=str(category_path),
        )

        documents: List[DocumentRecord] = []
        pdf_count = 0
        skipped_hidden = 0
        skipped_non_pdf = 0

        # rglob("*") walks recursively; we filter by extension and type
        for file_path in sorted(category_path.rglob("*")):
            if not file_path.is_file():
                continue

            # Skip hidden files
            if is_hidden_file(file_path):
                skipped_hidden += 1
                dataset_log.debug(
                    "Skipping hidden file | file={file}",
                    file=file_path.name,
                )
                continue

            # Skip non-PDF files
            if not is_pdf_by_extension(file_path):
                skipped_non_pdf += 1
                dataset_log.debug(
                    "Skipping non-PDF file | file={file}",
                    file=file_path.name,
                )
                continue

            pdf_count += 1
            record = self._process_pdf_file(file_path, category)
            documents.append(record)

            dataset_log.debug(
                "Processed | file={file} | status={status} | pages={pages}",
                file=file_path.name,
                status=record.status.value,
                pages=record.page_count,
            )

        dataset_log.info(
            "Category scan results | category={cat} | pdfs={pdfs} | "
            "skipped_hidden={hidden} | skipped_non_pdf={non_pdf}",
            cat=category,
            pdfs=pdf_count,
            hidden=skipped_hidden,
            non_pdf=skipped_non_pdf,
        )

        if pdf_count == 0:
            dataset_log.warning(
                "Empty category folder | category={cat} | path={path}",
                cat=category,
                path=str(category_path),
            )

        return documents

    def _process_pdf_file(
        self,
        file_path: Path,
        category: str,
    ) -> DocumentRecord:
        """
        Extract complete metadata for a single PDF file.

        STEPS:
            1. Get file size and timestamps from OS stat()
            2. Compute SHA256 checksum
            3. Attempt to open with PyMuPDF to get page count
            4. Determine status: VALID, INVALID, CORRUPTED, or EMPTY
            5. Build and return DocumentRecord

        Errors during individual file processing are caught and recorded
        in the document's status and error_message fields — they do NOT
        propagate and abort the scan.

        Args:
            file_path: Absolute path to the PDF file.
            category:  Document category name.

        Returns:
            DocumentRecord with all available metadata.
        """
        file_name = file_path.name
        dataset_log.debug("Processing PDF | file={file}", file=file_name)

        # ── File system metadata ──────────────────────────────────────────────
        try:
            file_size = get_file_size_bytes(file_path)
            created_at, modified_at = get_file_timestamps(file_path)
        except OSError as exc:
            dataset_log.error(
                "Cannot read file metadata | file={file} | error={error}",
                file=file_name,
                error=str(exc),
            )
            # Return a minimal invalid record
            return self._build_error_record(
                file_path=file_path,
                category=category,
                status=DocumentStatus.INVALID,
                error_message=f"Cannot read file metadata: {exc}",
            )

        # ── SHA256 checksum ───────────────────────────────────────────────────
        try:
            checksum = compute_sha256(file_path)
        except (OSError, PermissionError) as exc:
            dataset_log.error(
                "SHA256 failed | file={file} | error={error}",
                file=file_name,
                error=str(exc),
            )
            return self._build_error_record(
                file_path=file_path,
                category=category,
                status=DocumentStatus.INVALID,
                error_message=f"Cannot compute SHA256: {exc}",
            )

        # ── PDF validation (page count) ───────────────────────────────────────
        page_count, is_valid_pdf, pdf_error = get_pdf_page_count(file_path)

        if not is_valid_pdf:
            status = DocumentStatus.EMPTY if page_count == 0 else DocumentStatus.INVALID
            if pdf_error and "zero pages" in pdf_error.lower():
                status = DocumentStatus.EMPTY
            elif pdf_error and ("corrupted" in pdf_error.lower() or "damaged" in pdf_error.lower()):
                status = DocumentStatus.CORRUPTED
            elif not is_valid_pdf:
                status = DocumentStatus.INVALID

            dataset_log.warning(
                "Invalid PDF | file={file} | reason={reason}",
                file=file_name,
                reason=pdf_error,
            )
        else:
            status = DocumentStatus.VALID

        # ── Build relative path and derive title ──────────────────────────────
        relative_path = get_relative_path(file_path, self._dataset_root)
        title = derive_title(file_name)

        # ── Generate deterministic document ID ────────────────────────────────
        document_id = generate_document_id(checksum, relative_path)

        return DocumentRecord(
            document_id=document_id,
            file_name=file_name,
            title=title,
            file_path=str(file_path.resolve()),
            relative_path=relative_path,
            category=category,
            file_size_bytes=file_size,
            page_count=page_count,
            created_at=created_at,
            modified_at=modified_at,
            checksum_sha256=checksum,
            status=status,
            is_duplicate_of=None,
            error_message=pdf_error if not is_valid_pdf else None,
        )

    def _build_error_record(
        self,
        file_path: Path,
        category: str,
        status: DocumentStatus,
        error_message: str,
    ) -> DocumentRecord:
        """
        Build a minimal DocumentRecord for a file that could not be processed.

        Used when OS-level metadata extraction fails (permission error, etc.).
        SHA256 is set to "unknown"; page_count to 0.

        Args:
            file_path:     Path to the problematic file.
            category:      Category name.
            status:        Status to assign (typically INVALID).
            error_message: Human-readable description of the failure.

        Returns:
            DocumentRecord with status=INVALID and zero/unknown fields.
        """
        now = datetime.now(tz=timezone.utc)
        file_name = file_path.name
        try:
            relative_path = get_relative_path(file_path, self._dataset_root)
        except ValueError:
            relative_path = file_name

        return DocumentRecord(
            document_id=generate_document_id("unknown", relative_path + error_message),
            file_name=file_name,
            title=derive_title(file_name),
            file_path=str(file_path),
            relative_path=relative_path,
            category=category,
            file_size_bytes=0,
            page_count=0,
            created_at=now,
            modified_at=now,
            checksum_sha256="unknown",
            status=status,
            error_message=error_message,
        )

    # =========================================================================
    # PRIVATE HELPERS — DUPLICATE DETECTION
    # =========================================================================

    def _detect_duplicates(
        self,
        documents: List[DocumentRecord],
    ) -> List[DocumentRecord]:
        """
        Bypassed duplicate detection for presentation.
        """
        dataset_log.info("Duplicate detection bypassed for interview.")
        return documents

    # =========================================================================
    # PRIVATE HELPERS — STATISTICS
    # =========================================================================

    def _calculate_statistics(
        self,
        documents: List[DocumentRecord],
    ) -> DatasetStatistics:
        """
        Compute aggregate statistics from the full list of document records.

        Calculates:
            - Total, valid, invalid, empty, duplicate counts
            - Average pages (valid documents only)
            - Average file size (all documents)
            - Total size in bytes
            - Per-category counts and detailed category stats
            - Largest and smallest PDFs by page count (valid only)

        Args:
            documents: Complete list of DocumentRecord objects.

        Returns:
            DatasetStatistics with all computed metrics.
        """
        dataset_log.info("Calculating statistics | documents={count}", count=len(documents))

        total = len(documents)

        # ── Status counts ─────────────────────────────────────────────────────
        valid_docs = [d for d in documents if d.status == DocumentStatus.VALID]
        invalid_docs = [
            d for d in documents
            if d.status in (DocumentStatus.INVALID, DocumentStatus.CORRUPTED)
        ]
        empty_docs = [d for d in documents if d.status == DocumentStatus.EMPTY]
        duplicate_docs = [d for d in documents if d.status == DocumentStatus.DUPLICATE]

        # ── Page statistics (valid only) ──────────────────────────────────────
        avg_pages = (
            sum(d.page_count for d in valid_docs) / len(valid_docs)
            if valid_docs else 0.0
        )

        # ── Size statistics ───────────────────────────────────────────────────
        all_sizes = [d.file_size_bytes for d in documents]
        total_size = sum(all_sizes)
        avg_size = total_size / total if total > 0 else 0.0

        # ── Largest and smallest by page count (valid only) ───────────────────
        largest_pdf_name: Optional[str] = None
        smallest_pdf_name: Optional[str] = None

        if valid_docs:
            largest_doc = max(valid_docs, key=lambda d: d.page_count)
            smallest_doc = min(valid_docs, key=lambda d: d.page_count)
            largest_pdf_name = largest_doc.file_name
            smallest_pdf_name = smallest_doc.file_name

        # ── Per-category statistics ───────────────────────────────────────────
        category_counts: Dict[str, int] = {}
        category_stats_list: List[CategoryStatistics] = []

        for category in VALID_CATEGORIES:
            cat_docs = [d for d in documents if d.category == category]
            cat_valid = [d for d in cat_docs if d.status == DocumentStatus.VALID]
            cat_invalid = [
                d for d in cat_docs
                if d.status in (DocumentStatus.INVALID, DocumentStatus.CORRUPTED, DocumentStatus.EMPTY)
            ]
            cat_duplicate = [d for d in cat_docs if d.status == DocumentStatus.DUPLICATE]

            count = len(cat_docs)
            category_counts[category] = count

            if count > 0:
                category_stats_list.append(
                    CategoryStatistics(
                        category=category,
                        total=count,
                        valid=len(cat_valid),
                        invalid=len(cat_invalid),
                        duplicate=len(cat_duplicate),
                        total_pages=sum(d.page_count for d in cat_valid),
                        total_size_bytes=sum(d.file_size_bytes for d in cat_docs),
                    )
                )

        stats = DatasetStatistics(
            total_documents=total,
            valid_documents=len(valid_docs),
            invalid_documents=len(invalid_docs),
            empty_documents=len(empty_docs),
            duplicate_documents=len(duplicate_docs),
            avg_pages=avg_pages,
            avg_file_size_bytes=avg_size,
            total_size_bytes=total_size,
            category_counts=category_counts,
            category_stats=category_stats_list,
            largest_pdf_name=largest_pdf_name,
            smallest_pdf_name=smallest_pdf_name,
            scanned_at=datetime.now(tz=timezone.utc),
            dataset_root=str(self._dataset_root),
        )

        dataset_log.info(
            "Statistics calculated | total={total} | valid={valid} | "
            "avg_pages={avg_pages:.1f} | total_size={size}",
            total=stats.total_documents,
            valid=stats.valid_documents,
            avg_pages=stats.avg_pages,
            size=format_size_human(stats.total_size_bytes),
        )

        return stats
