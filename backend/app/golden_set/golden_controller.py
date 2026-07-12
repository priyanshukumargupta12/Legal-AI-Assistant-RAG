"""
app/golden_set/golden_controller.py
=====================================
HTTP controller for the Golden Set Management Module.

PURPOSE:
    Thin translation layer between FastAPI HTTP requests and GoldenSetService.

    This controller:
        - Registers all /api/v1/golden/* routes
        - Validates route parameters
        - Calls GoldenSetService methods
        - Converts domain models to HTTP responses using golden_schemas
        - Handles file uploads (multipart/form-data)
        - Handles file downloads (CSV, XLSX)

    It contains NO business logic — all processing is delegated to
    GoldenSetService. Controllers are deliberately thin.

ENDPOINTS:
    POST /api/v1/golden/import         — Trigger auto-import from metadata/
    POST /api/v1/golden/upload         — Upload a custom golden set file
    GET  /api/v1/golden/statistics     — Return latest statistics
    GET  /api/v1/golden/report         — Return full validation report
    GET  /api/v1/golden/records        — Paginated list of valid records
    GET  /api/v1/golden/export/csv     — Download validated_golden_set.csv
    GET  /api/v1/golden/export/xlsx    — Download validated_golden_set.xlsx

DEPENDENCY INJECTION:
    GoldenSetService is provided via FastAPI's Depends() mechanism.

SOLID:
    Single Responsibility — HTTP routing and response formatting only.
    Dependency Inversion  — depends on GoldenSetService abstraction.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.api.responses.standard_response import StandardResponse
from app.core.config import get_settings
from app.core.exceptions import GoldenSetImportError
from app.golden_set.golden_logger import golden_log
from app.golden_set.golden_repository import FileSystemGoldenSetRepository
from app.golden_set.golden_schemas import (
    GoldenRecordSchema,
    GoldenRecordsListSchema,
    GoldenSetStatisticsSchema,
    ImportResultSchema,
    ValidationReportSchema,
)
from app.golden_set.golden_service import GoldenSetService

# ─── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(
    prefix="/golden",
    tags=["Golden Set Management"],
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Resource not found"},
        422: {"description": "Validation error or import failure"},
    },
)


# =============================================================================
# DEPENDENCY INJECTION FACTORY
# =============================================================================

def get_golden_service() -> GoldenSetService:
    """
    FastAPI dependency factory for GoldenSetService.

    Constructs the service with all its dependencies injected:
        - FileSystemGoldenSetRepository (writes to metadata/)
        - metadata_dir path from application settings

    Used via: `service: GoldenSetService = Depends(get_golden_service)`

    Returns:
        Fully configured GoldenSetService instance.
    """
    settings = get_settings()
    metadata_dir = Path(settings.metadata_path).resolve()
    repository = FileSystemGoldenSetRepository(metadata_dir=metadata_dir)
    return GoldenSetService(repository=repository, metadata_dir=metadata_dir)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/import",
    response_model=StandardResponse,
    summary="Auto-import Golden Set from metadata directory",
    description=(
        "Automatically locates and imports golden_set.csv or golden_set.xlsx "
        "from the metadata/ directory. Validates every record, computes statistics, "
        "builds source→dataset mappings, and exports validated CSV/XLSX. "
        "Returns the import result with statistics and validation report."
    ),
    response_description="Import result with statistics, validation report, and source mappings.",
)
async def auto_import_golden_set(
    service: GoldenSetService = Depends(get_golden_service),
) -> StandardResponse:
    """
    Trigger automatic golden set import from the metadata directory.

    Searches for golden_set.csv first, then golden_set.xlsx.
    Runs the full import pipeline: read → validate → statistics → persist.

    Returns:
        StandardResponse containing ImportResultSchema payload.

    Raises:
        HTTPException 404: If neither golden_set.csv nor golden_set.xlsx exists.
        HTTPException 422: If the file exists but cannot be parsed.
        HTTPException 500: On unexpected failures.
    """
    golden_log.info("API: POST /golden/import — auto-import requested")

    try:
        result = service.auto_import()
    except GoldenSetImportError as exc:
        golden_log.error("Auto-import failed | error={err}", err=exc.message)
        if "not found" in exc.message.lower():
            raise HTTPException(status_code=404, detail=exc.message) from exc
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except Exception as exc:
        golden_log.exception("Unexpected auto-import error | error={err}", err=str(exc))
        raise HTTPException(
            status_code=500,
            detail="Golden set import failed due to an unexpected error.",
        ) from exc

    schema = ImportResultSchema.from_import_result(result)

    golden_log.info(
        "API: auto-import complete | file={file} | valid={v}/{t}",
        file=result.source_file_name,
        v=result.validation_report.valid_count,
        t=result.validation_report.total_rows,
    )

    return StandardResponse.success(
        data=schema.model_dump(),
        message=schema.message,
    )


@router.post(
    "/upload",
    response_model=StandardResponse,
    summary="Upload a custom Golden Set file",
    description=(
        "Accept a CSV or Excel (.xlsx) golden set file upload via multipart form. "
        "Runs the full import pipeline: read → validate → statistics → persist. "
        "The uploaded file is NOT saved permanently — only the validated output files are kept."
    ),
    response_description="Import result with statistics, validation report, and source mappings.",
)
async def upload_golden_set(
    file: UploadFile = File(
        ...,
        description="Golden set file to upload. Must be .csv or .xlsx format.",
    ),
    service: GoldenSetService = Depends(get_golden_service),
) -> StandardResponse:
    """
    Upload and import a custom golden set file.

    Accepts multipart/form-data with a single file field named 'file'.
    Maximum file size: 50 MB.

    Args:
        file:    The uploaded file (UploadFile from FastAPI).
        service: Injected GoldenSetService.

    Returns:
        StandardResponse containing ImportResultSchema payload.

    Raises:
        HTTPException 400: If the file format is unsupported.
        HTTPException 413: If the file exceeds 50 MB.
        HTTPException 422: If the file cannot be parsed or has no valid records.
        HTTPException 500: On unexpected failures.
    """
    golden_log.info(
        "API: POST /golden/upload | filename={name} | content_type={ct}",
        name=file.filename,
        ct=file.content_type,
    )

    # Validate file format
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: '{suffix}'. Expected .csv or .xlsx",
        )

    # Read file content
    content = await file.read()

    # Check file size (50 MB limit)
    max_size = 50 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) / 1024 / 1024:.1f} MB). Maximum: 50 MB.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = service.import_from_bytes(content=content, filename=file.filename)
    except GoldenSetImportError as exc:
        golden_log.error("Upload import failed | error={err}", err=exc.message)
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except Exception as exc:
        golden_log.exception("Unexpected upload error | error={err}", err=str(exc))
        raise HTTPException(
            status_code=500,
            detail="Upload failed due to an unexpected error.",
        ) from exc

    schema = ImportResultSchema.from_import_result(result)

    golden_log.info(
        "API: upload complete | file={file} | valid={v}/{t}",
        file=result.source_file_name,
        v=result.validation_report.valid_count,
        t=result.validation_report.total_rows,
    )

    return StandardResponse.success(
        data=schema.model_dump(),
        message=schema.message,
    )


@router.get(
    "/statistics",
    response_model=StandardResponse,
    summary="Get Golden Set statistics",
    description=(
        "Return the computed statistics from the last golden set import. "
        "Reads from the persisted golden_set_statistics.json without re-importing."
    ),
)
async def get_statistics(
    service: GoldenSetService = Depends(get_golden_service),
) -> StandardResponse:
    """
    Return the golden set statistics dashboard data.

    Reads from the previously persisted statistics JSON.

    Returns:
        StandardResponse containing GoldenSetStatisticsSchema payload.

    Raises:
        HTTPException 404: If no import has been performed yet.
    """
    golden_log.info("API: GET /golden/statistics")

    statistics = service.get_statistics()
    if statistics is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No golden set statistics found. "
                "Please run POST /api/v1/golden/import first."
            ),
        )

    schema = GoldenSetStatisticsSchema.from_statistics(statistics)
    return StandardResponse.success(
        data=schema.model_dump(),
        message="Golden set statistics retrieved successfully.",
    )


@router.get(
    "/report",
    response_model=StandardResponse,
    summary="Get validation report",
    description=(
        "Return the full validation report from the last golden set import, "
        "including all field-level errors with row numbers and descriptions."
    ),
)
async def get_validation_report(
    service: GoldenSetService = Depends(get_golden_service),
) -> StandardResponse:
    """
    Return the golden set validation report.

    Reads from the previously persisted validation report JSON.

    Returns:
        StandardResponse containing the raw validation report dict.

    Raises:
        HTTPException 404: If no import has been performed yet.
    """
    golden_log.info("API: GET /golden/report")

    report_data = service.get_validation_report()
    if report_data is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No validation report found. "
                "Please run POST /api/v1/golden/import first."
            ),
        )

    return StandardResponse.success(
        data=report_data,
        message="Validation report retrieved successfully.",
    )


@router.get(
    "/records",
    response_model=StandardResponse,
    summary="List golden records (paginated)",
    description=(
        "Return a paginated list of validated golden records from the last import. "
        "Supports filtering by category and status."
    ),
)
async def list_records(
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=50, ge=1, le=200, description="Records per page."),
    category: Optional[str] = Query(
        default=None,
        description="Filter by category: Acts | CourtJudgement | Tax | Legal_opinion",
    ),
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: valid | invalid | duplicate | rejected",
    ),
    service: GoldenSetService = Depends(get_golden_service),
) -> StandardResponse:
    """
    Return paginated golden records.

    Reads from the persisted validated_golden_set.csv without re-importing.

    Args:
        page:      Page number (1-based).
        page_size: Records per page (max 200).
        category:  Optional category filter.
        status:    Optional status filter.
        service:   Injected GoldenSetService.

    Returns:
        StandardResponse containing GoldenRecordsListSchema payload.

    Raises:
        HTTPException 404: If no import has been performed yet.
        HTTPException 400: If invalid filter values are provided.
    """
    golden_log.info(
        "API: GET /golden/records | page={page} | page_size={ps} | "
        "category={cat} | status={status}",
        page=page,
        ps=page_size,
        cat=category,
        status=status,
    )

    # Validate category filter
    from app.core.constants import VALID_CATEGORIES
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {list(VALID_CATEGORIES)}",
        )

    # Validate status filter
    valid_statuses = {"valid", "invalid", "duplicate", "rejected"}
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of: {sorted(valid_statuses)}",
        )

    raw_rows = service.get_validated_records_raw()
    if raw_rows is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No validated golden set found. "
                "Please run POST /api/v1/golden/import first."
            ),
        )

    # Build GoldenRecord objects from CSV rows for schema conversion
    from app.golden_set.golden_models import GoldenRecord, GoldenRecordStatus

    def _row_to_record(row: dict, idx: int) -> GoldenRecord:
        """Convert a CSV row dict back to a minimal GoldenRecord for API response."""
        try:
            page_num = int(row.get("page_number", 0) or 0)
        except (ValueError, TypeError):
            page_num = 0

        status_str = row.get("status", "valid")
        try:
            rec_status = GoldenRecordStatus(status_str)
        except ValueError:
            rec_status = GoldenRecordStatus.VALID

        return GoldenRecord(
            query=row.get("query", ""),
            expected_answer=row.get("expected_answer", ""),
            source_document=row.get("source_document", ""),
            page_number=page_num,
            category=row.get("category", ""),
            citation=row.get("citation") or None,
            difficulty=row.get("difficulty") or None,
            tags=row.get("tags") or None,
            notes=row.get("notes") or None,
            row_number=int(row.get("row_number", idx) or idx),
            status=rec_status,
        )

    all_records = [_row_to_record(row, i) for i, row in enumerate(raw_rows, start=2)]

    # Apply filters
    filtered = all_records
    if category:
        filtered = [r for r in filtered if r.category == category]
    if status:
        filtered = [r for r in filtered if r.status.value == status]

    total = len(filtered)
    total_valid = sum(1 for r in all_records if r.status == GoldenRecordStatus.VALID)
    total_pages = max(1, math.ceil(total / page_size))

    # Paginate
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_records = filtered[start_idx:end_idx]

    record_schemas = [GoldenRecordSchema.from_record(r) for r in page_records]

    result = GoldenRecordsListSchema(
        total=total,
        valid_total=total_valid,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        records=record_schemas,
        category_filter=category,
        status_filter=status,
    )

    golden_log.info(
        "API: records returned | total={total} | page={page}/{pages}",
        total=total,
        page=page,
        pages=total_pages,
    )

    return StandardResponse.success(
        data=result.model_dump(),
        message=f"Retrieved {len(page_records)} records (page {page} of {total_pages}).",
    )


@router.get(
    "/export/csv",
    summary="Download validated golden set CSV",
    description="Download the validated_golden_set.csv generated by the last import.",
    response_class=FileResponse,
)
async def export_csv(
    service: GoldenSetService = Depends(get_golden_service),
) -> FileResponse:
    """
    Serve validated_golden_set.csv as a file download.

    Raises:
        HTTPException 404: If validated_golden_set.csv does not exist yet.
    """
    csv_path = service.export_validated_csv_path()
    if csv_path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "validated_golden_set.csv not found. "
                "Run POST /api/v1/golden/import first."
            ),
        )

    golden_log.info("API: GET /golden/export/csv — serving {path}", path=str(csv_path))
    return FileResponse(
        path=str(csv_path),
        media_type="text/csv",
        filename="validated_golden_set.csv",
        headers={"Content-Disposition": 'attachment; filename="validated_golden_set.csv"'},
    )


@router.get(
    "/export/xlsx",
    summary="Download validated golden set XLSX",
    description="Download the validated_golden_set.xlsx generated by the last import with status-color formatting.",
    response_class=FileResponse,
)
async def export_xlsx(
    service: GoldenSetService = Depends(get_golden_service),
) -> FileResponse:
    """
    Serve validated_golden_set.xlsx as a file download.

    Raises:
        HTTPException 404: If validated_golden_set.xlsx does not exist yet.
    """
    xlsx_path = service.export_validated_xlsx_path()
    if xlsx_path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "validated_golden_set.xlsx not found. "
                "Run POST /api/v1/golden/import first."
            ),
        )

    golden_log.info("API: GET /golden/export/xlsx — serving {path}", path=str(xlsx_path))
    return FileResponse(
        path=str(xlsx_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="validated_golden_set.xlsx",
        headers={"Content-Disposition": 'attachment; filename="validated_golden_set.xlsx"'},
    )
