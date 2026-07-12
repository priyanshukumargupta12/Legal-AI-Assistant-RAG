"""
app/golden_set/golden_service.py
==================================
Orchestration service for the Golden Set Management Module.

PURPOSE:
    Implements all golden set business logic by coordinating:
        - CSVImporter / ExcelImporter (file reading)
        - GoldenSetValidator (record validation)
        - StatisticsEngine (metrics computation)
        - GoldenSetRepository (persistence)

    This is the primary entry point for all golden set operations.
    Controllers call service methods — never touch importers or validators
    directly.

RESPONSIBILITIES:
    1. Auto-import: detect golden_set.csv or golden_set.xlsx from metadata/
    2. Manual import: accept an arbitrary file path
    3. Upload import: accept raw bytes with a filename
    4. Export: serve the validated CSV or XLSX file
    5. Query: return persisted statistics or validation report

DESIGN:
    - Dependency Injection: repository injected via constructor
    - All public methods return domain models (not HTTP responses)
    - Private helpers coordinate the import pipeline steps
    - Comprehensive logging at every stage

SOLID:
    Single Responsibility — golden set orchestration only.
    Dependency Inversion  — depends on GoldenSetRepository abstraction.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.core.exceptions import GoldenSetImportError
from app.golden_set.csv_importer import CSVImporter
from app.golden_set.excel_importer import ExcelImporter
from app.golden_set.golden_logger import golden_log
from app.golden_set.golden_models import (
    ExportFormat,
    GoldenRecord,
    GoldenSetExportConfig,
    GoldenSetImportResult,
    GoldenSetStatistics,
    GoldenSetUseCase,
    SourceMapping,
    ValidationReport,
)
from app.golden_set.golden_repository import GoldenSetRepository
from app.golden_set.golden_utils import map_source_to_dataset
from app.golden_set.statistics import StatisticsEngine
from app.golden_set.validator import GoldenSetValidator


# ─── Output file names ─────────────────────────────────────────────────────────
_VALIDATED_CSV_NAME = "validated_golden_set.csv"
_VALIDATED_XLSX_NAME = "validated_golden_set.xlsx"
_REPORT_JSON_NAME = "golden_set_validation_report.json"
_STATISTICS_JSON_NAME = "golden_set_statistics.json"


class GoldenSetService:
    """
    Orchestrates the complete golden set import, validation, and export pipeline.

    CURRENT RESPONSIBILITIES:
        1. Auto-import: detect golden_set.csv or golden_set.xlsx from metadata/
        2. Manual import: accept an arbitrary file path
        3. Upload import: accept raw bytes with a filename
        4. Standard export: serve the validated CSV or XLSX file
        5. Query: return persisted statistics or validation report

    EXTENSIBILITY (use export_for_use_case() when adapters are registered):
        6. Use-case export: delegate to GoldenSetRegistry for adapter-driven
           export to any registered format (JSONL, Parquet, etc.)

    See golden_extensions.py for the GoldenSetAdapter, GoldenSetExporter,
    DataSplitter, and GoldenSetRegistry interfaces that enable extension.

    Args:
        repository:   Injected GoldenSetRepository for file persistence.
        metadata_dir: Path to the metadata/ directory (source of golden_set files).
    """

    def __init__(
        self,
        repository: GoldenSetRepository,
        metadata_dir: Path,
    ) -> None:
        self._repository = repository
        self._metadata_dir = metadata_dir
        self._csv_importer = CSVImporter()
        self._excel_importer = ExcelImporter()
        self._validator = GoldenSetValidator()
        self._stats_engine = StatisticsEngine()

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def auto_import(self) -> GoldenSetImportResult:
        """
        Automatically locate and import the golden set from the metadata directory.

        Priority:
            1. golden_set.csv  (preferred — always present)
            2. golden_set.xlsx (fallback if CSV not found)

        Returns:
            GoldenSetImportResult with records, report, statistics, and mappings.

        Raises:
            GoldenSetImportError: If neither golden_set.csv nor golden_set.xlsx exists.
        """
        golden_log.info(
            "Auto-import started | searching in metadata_dir={dir}",
            dir=str(self._metadata_dir),
        )

        csv_path = self._metadata_dir / "golden_set.csv"
        xlsx_path = self._metadata_dir / "golden_set.xlsx"

        if csv_path.exists():
            golden_log.info("Found golden_set.csv — importing CSV")
            return self.import_from_file(csv_path)
        elif xlsx_path.exists():
            golden_log.info("Found golden_set.xlsx — importing Excel")
            return self.import_from_file(xlsx_path)
        else:
            raise GoldenSetImportError(
                message=(
                    "No golden set file found in metadata directory. "
                    "Expected: golden_set.csv or golden_set.xlsx"
                )
            )

    def import_from_file(self, file_path: Path) -> GoldenSetImportResult:
        """
        Import, validate, compute statistics, and persist a golden set file.

        Supports CSV (.csv) and Excel (.xlsx) files.

        Pipeline stages:
            1. Read file (CSVImporter or ExcelImporter)
            2. Validate all records (GoldenSetValidator)
            3. Build source→dataset mappings
            4. Compute statistics (StatisticsEngine)
            5. Persist outputs (GoldenSetRepository)
            6. Return GoldenSetImportResult

        Args:
            file_path: Absolute path to the golden set file.

        Returns:
            GoldenSetImportResult with all pipeline outputs.

        Raises:
            GoldenSetImportError: On read failure or unsupported file format.
        """
        start_time = time.perf_counter()
        suffix = file_path.suffix.lower()

        golden_log.info(
            "Import started | file={file} | format={fmt}",
            file=file_path.name,
            fmt=suffix,
        )

        # ── Stage 1: Read file ────────────────────────────────────────────────
        if suffix == ".csv":
            raw_rows = self._csv_importer.import_file(file_path)
        elif suffix in (".xlsx", ".xls"):
            raw_rows = self._excel_importer.import_file(file_path)
        else:
            raise GoldenSetImportError(
                message=f"Unsupported file format: '{suffix}'. Expected .csv or .xlsx"
            )

        golden_log.info(
            "File read complete | rows={count}",
            count=len(raw_rows),
        )

        # ── Stage 2: Validate records ─────────────────────────────────────────
        records, validation_report = self._validator.validate_records(
            rows=raw_rows,
            source_file=file_path.name,
        )

        golden_log.info(
            "Validation complete | valid={v} | invalid={i} | duplicate={d}",
            v=validation_report.valid_count,
            i=validation_report.invalid_count,
            d=validation_report.duplicate_count,
        )

        # ── Stage 3: Build source→dataset mappings ────────────────────────────
        documents_csv_path = self._metadata_dir / "documents.csv"
        source_mappings = self._build_source_mappings(records, documents_csv_path)

        golden_log.info(
            "Source mappings built | unique_sources={count} | indexed={indexed}",
            count=len(source_mappings),
            indexed=sum(1 for m in source_mappings if m.is_indexed),
        )

        # ── Stage 4: Compute statistics ───────────────────────────────────────
        statistics = self._stats_engine.compute(records, source_file=file_path.name)

        golden_log.info(
            "Statistics computed | total={t} | valid={v} | categories={cats}",
            t=statistics.total_queries,
            v=statistics.valid_queries,
            cats=list(statistics.category_distribution.keys()),
        )

        # ── Stage 5: Persist outputs ──────────────────────────────────────────
        self._repository.save_validated_csv(
            records,
            self._metadata_dir / _VALIDATED_CSV_NAME,
        )
        self._repository.save_validated_xlsx(
            records,
            self._metadata_dir / _VALIDATED_XLSX_NAME,
        )
        self._repository.save_report(
            validation_report,
            self._metadata_dir / _REPORT_JSON_NAME,
        )
        self._repository.save_statistics(
            statistics,
            self._metadata_dir / _STATISTICS_JSON_NAME,
        )

        # ── Stage 6: Build result ─────────────────────────────────────────────
        duration = time.perf_counter() - start_time
        result = GoldenSetImportResult(
            records=records,
            validation_report=validation_report,
            statistics=statistics,
            source_mappings=source_mappings,
            source_file_name=file_path.name,
            import_duration_s=duration,
        )

        golden_log.info(
            "Import finished | file={file} | duration={dur:.2f}s | "
            "valid={v}/{t} records",
            file=file_path.name,
            dur=duration,
            v=validation_report.valid_count,
            t=validation_report.total_rows,
        )

        return result

    def import_from_bytes(
        self,
        content: bytes,
        filename: str,
    ) -> GoldenSetImportResult:
        """
        Import a golden set from raw bytes (uploaded via HTTP multipart form).

        Writes the bytes to a temporary file in metadata/, imports it,
        then cleans up.

        Args:
            content:  Raw file bytes from the uploaded file.
            filename: Original filename (used to determine format).

        Returns:
            GoldenSetImportResult with all pipeline outputs.

        Raises:
            GoldenSetImportError: On write failure or unsupported format.
        """
        suffix = Path(filename).suffix.lower()
        if suffix not in (".csv", ".xlsx"):
            raise GoldenSetImportError(
                message=f"Unsupported upload format: '{suffix}'. Expected .csv or .xlsx"
            )

        # Write to a temp file in metadata dir
        temp_path = self._metadata_dir / f"_upload_{filename}"
        try:
            temp_path.write_bytes(content)
            golden_log.info(
                "Upload written to temp file | path={path} | size={size}",
                path=str(temp_path),
                size=len(content),
            )
            return self.import_from_file(temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def get_statistics(self) -> Optional[GoldenSetStatistics]:
        """
        Return persisted GoldenSetStatistics from the last import.

        Reads from metadata/golden_set_statistics.json without re-importing.

        Returns:
            GoldenSetStatistics if a previous import exists, otherwise None.
        """
        import json
        stats_path = self._metadata_dir / _STATISTICS_JSON_NAME
        if not stats_path.exists():
            return None

        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            from datetime import datetime, timezone
            from app.golden_set.golden_models import CategoryStats

            category_stats_list = [
                CategoryStats(
                    category=cs["category"],
                    total=cs["total"],
                    valid=cs["valid"],
                    invalid=cs["invalid"],
                    duplicate=cs["duplicate"],
                    avg_query_len=cs.get("avg_query_len", 0.0),
                )
                for cs in data.get("category_stats", [])
            ]

            return GoldenSetStatistics(
                total_queries=data.get("total_queries", 0),
                valid_queries=data.get("valid_queries", 0),
                invalid_queries=data.get("invalid_queries", 0),
                duplicate_queries=data.get("duplicate_queries", 0),
                rejected_queries=data.get("rejected_queries", 0),
                category_distribution=data.get("category_distribution", {}),
                category_stats=category_stats_list,
                avg_query_length=data.get("avg_query_length", 0.0),
                avg_answer_length=data.get("avg_answer_length", 0.0),
                unique_source_docs=data.get("unique_source_docs", 0),
                computed_at=datetime.fromisoformat(
                    data["computed_at"].rstrip("Z")
                ).replace(tzinfo=timezone.utc),
                source_file=data.get("source_file", ""),
            )
        except Exception as exc:
            golden_log.error(
                "Failed to load statistics from {path}: {err}",
                path=str(stats_path),
                err=str(exc),
            )
            return None

    def get_validation_report(self) -> Optional[Dict]:
        """
        Return the raw validation report JSON from the last import.

        Returns:
            dict from golden_set_validation_report.json, or None if not found.
        """
        import json
        report_path = self._metadata_dir / _REPORT_JSON_NAME
        if not report_path.exists():
            return None
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            golden_log.error(
                "Failed to load validation report from {path}: {err}",
                path=str(report_path),
                err=str(exc),
            )
            return None

    def get_validated_records_raw(self) -> Optional[List[Dict]]:
        """
        Return all validated records from the persisted CSV.

        Returns:
            List of raw row dicts from validated_golden_set.csv, or None.
        """
        csv_path = self._metadata_dir / _VALIDATED_CSV_NAME
        return self._repository.load_validated_records(csv_path)

    def export_validated_csv_path(self) -> Optional[Path]:
        """Return the path to validated_golden_set.csv if it exists."""
        path = self._metadata_dir / _VALIDATED_CSV_NAME
        return path if path.exists() else None

    def export_validated_xlsx_path(self) -> Optional[Path]:
        """Return the path to validated_golden_set.xlsx if it exists."""
        path = self._metadata_dir / _VALIDATED_XLSX_NAME
        return path if path.exists() else None

    def export_for_use_case(
        self,
        config: GoldenSetExportConfig,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Export the validated golden set for a specific downstream use case.

        This method delegates to the GoldenSetRegistry to find the correct
        GoldenSetAdapter + GoldenSetExporter pair for the given config, then
        runs the full export pipeline:

            1. Load validated records from CSV
            2. Run pre-export pipeline hooks
            3. Adapter filters + transforms records to use-case format
            4. DataSplitter assigns train/val/test splits (if configured)
            5. Exporter writes the output file
            6. Run post-export pipeline hooks

        AVAILABILITY:
            This method requires at least one GoldenSetAdapter and one
            GoldenSetExporter to be registered in the GoldenSetRegistry.
            If none are registered, it raises NotImplementedError.
            Concrete adapters are NOT yet implemented.

        Args:
            config:      GoldenSetExportConfig describing the target use case,
                         format, split strategy, and field mapping.
            output_path: Optional explicit output path. If None, a default
                         path in metadata/ is derived from the use case name.

        Returns:
            Path to the written output file.

        Raises:
            NotImplementedError:  If no adapter is registered for config.use_case.
            GoldenSetImportError: If no validated records exist to export.
            KeyError:             If no exporter is registered for config.export_format.
        """
        # Late import to avoid circular dependency — golden_extensions imports golden_models
        from app.golden_set.golden_extensions import GoldenSetRegistry

        registry = GoldenSetRegistry.get_instance()

        # Validate that the required adapter + exporter are registered
        if not registry.is_adapter_registered(config.use_case):
            raise NotImplementedError(
                f"No adapter registered for use case '{config.use_case.value}'. "
                f"Register a GoldenSetAdapter via GoldenSetRegistry before calling "
                f"export_for_use_case()."
            )
        if not registry.is_exporter_registered(config.export_format):
            raise NotImplementedError(
                f"No exporter registered for format '{config.export_format.value}'. "
                f"Register a GoldenSetExporter via GoldenSetRegistry."
            )

        # Load validated records
        raw_rows = self.get_validated_records_raw()
        if raw_rows is None:
            raise GoldenSetImportError(
                message=(
                    "No validated records found. "
                    "Run auto_import() or import_from_file() first."
                )
            )

        # Reconstruct minimal GoldenRecord objects for adapter
        from app.golden_set.golden_models import GoldenRecord, GoldenRecordStatus, DataSplit
        records: List[GoldenRecord] = []
        for i, row in enumerate(raw_rows, start=2):
            try:
                page_num = int(float(row.get("page_number", 0) or 0))
            except (ValueError, TypeError):
                page_num = 0
            try:
                rec_status = GoldenRecordStatus(row.get("status", "valid"))
            except ValueError:
                rec_status = GoldenRecordStatus.VALID
            records.append(GoldenRecord(
                query=row.get("query", ""),
                expected_answer=row.get("expected_answer", ""),
                source_document=row.get("source_document", ""),
                page_number=page_num,
                category=row.get("category", ""),
                citation=row.get("citation") or None,
                difficulty=row.get("difficulty") or None,
                tags=row.get("tags") or None,
                notes=row.get("notes") or None,
                row_number=int(row.get("row_number", i) or i),
                status=rec_status,
            ))

        adapter  = registry.get_adapter(config.use_case)
        exporter = registry.get_exporter(config.export_format)
        hooks    = registry.get_hooks(config.use_case)

        # Determine output path
        if output_path is None:
            output_path = (
                self._metadata_dir
                / f"export_{config.use_case.value}.{config.export_format.value}"
            )

        # Run pre-export hooks
        for hook in hooks:
            try:
                hook.before_export(config, records)
            except Exception as exc:
                golden_log.warning(
                    "Pipeline hook before_export raised: {err}", err=str(exc)
                )

        # Transform records via adapter
        rows = adapter.batch_transform(records, config)

        # Write output via exporter
        written_path = exporter.export(rows, output_path, config)

        # Run post-export hooks
        for hook in hooks:
            try:
                hook.after_export(config, written_path, len(rows))
            except Exception as exc:
                golden_log.warning(
                    "Pipeline hook after_export raised: {err}", err=str(exc)
                )

        golden_log.info(
            "export_for_use_case complete | use_case={uc} | format={fmt} | "
            "rows={rows} | path={path}",
            uc=config.use_case.value,
            fmt=config.export_format.value,
            rows=len(rows),
            path=str(written_path),
        )

        return written_path

    def get_registry_summary(self) -> Dict:
        """
        Return a summary of all registered adapters, exporters, and hooks.

        Used by health-check endpoints and admin UIs to inspect which
        use-case extensions are currently available.

        Returns:
            Dict with keys: adapters, exporters, hooks.
            Returns {'adapters': {}, 'exporters': {}, 'hooks': {}} if
            no adapters or exporters have been registered yet.
        """
        from app.golden_set.golden_extensions import GoldenSetRegistry
        return GoldenSetRegistry.get_instance().describe()


    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _build_source_mappings(
        self,
        records: List[GoldenRecord],
        documents_csv_path: Path,
    ) -> List[SourceMapping]:
        """
        Build source→dataset mappings for all unique source documents.

        Args:
            records:              All GoldenRecord objects.
            documents_csv_path:   Path to documents.csv.

        Returns:
            List of SourceMapping objects, one per unique source document.
        """
        from app.golden_set.golden_models import GoldenRecordStatus as GRS

        # Collect unique source documents from valid records
        unique_sources = {
            r.source_document
            for r in records
            if r.source_document and r.status == GRS.VALID
        }

        mappings: List[SourceMapping] = []
        for source_doc in sorted(unique_sources):
            lookup = map_source_to_dataset(source_doc, documents_csv_path)
            mappings.append(SourceMapping(
                source_document=source_doc,
                document_id=lookup.get("document_id"),
                category=lookup.get("category"),
                page_count=lookup.get("page_count"),
                is_indexed=bool(lookup.get("is_indexed", False)),
            ))

        return mappings
