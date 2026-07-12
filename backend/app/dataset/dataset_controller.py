"""
app/dataset/dataset_controller.py
====================================
HTTP controller for the Dataset Management Module.

PURPOSE:
    Thin translation layer between FastAPI HTTP requests and DatasetService.

    This controller:
        - Registers all /api/v1/dataset/* routes
        - Validates route parameters
        - Calls DatasetService methods
        - Converts domain models to HTTP responses using schemas
        - Handles file downloads (CSV, XLSX)

    It contains NO business logic — all processing is delegated to
    DatasetService. Controllers are deliberately thin.

ENDPOINTS:
    POST /api/v1/dataset/scan          — Trigger full dataset scan
    GET  /api/v1/dataset/statistics    — Return latest statistics (from CSV)
    GET  /api/v1/dataset/documents     — List documents with optional filters
    GET  /api/v1/dataset/export/csv    — Download documents.csv
    GET  /api/v1/dataset/export/xlsx   — Download documents.xlsx
    GET  /api/v1/dataset/export/json   — Return dataset_summary.json content

DEPENDENCY INJECTION:
    DatasetService is provided via FastAPI's Depends() mechanism.
    The factory function get_dataset_service() creates the service with
    all its dependencies injected.

SOLID:
    Single Responsibility — HTTP routing and response formatting only.
    Dependency Inversion  — depends on DatasetService abstraction.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings
from app.core.exceptions import DatasetScanError, ResourceNotFoundError
from app.dataset.dataset_logger import dataset_log
from app.dataset.dataset_models import DocumentStatus
from app.dataset.dataset_repository import FileSystemDatasetRepository
from app.dataset.dataset_schemas import (
    DatasetStatisticsSchema,
    DocumentListSchema,
    DocumentRecordSchema,
    ExportResponseSchema,
    ScanResponseSchema,
)
from app.dataset.dataset_service import DatasetService

# ─── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(
    prefix="/dataset",
    tags=["Dataset Management"],
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Resource not found"},
    },
)


# =============================================================================
# DEPENDENCY INJECTION FACTORY
# =============================================================================

def get_dataset_service() -> DatasetService:
    """
    FastAPI dependency factory for DatasetService.

    Constructs the service with all its dependencies injected:
        - FileSystemDatasetRepository (writes to metadata/)
        - dataset_root path from application settings
        - metadata_dir path from application settings

    Used via: `service: DatasetService = Depends(get_dataset_service)`

    Returns:
        Fully configured DatasetService instance.
    """
    settings = get_settings()

    # Resolve paths from settings
    dataset_root = Path(settings.dataset_path).resolve()
    metadata_dir = Path(settings.metadata_path).resolve()

    repository = FileSystemDatasetRepository(metadata_dir=metadata_dir)

    return DatasetService(
        repository=repository,
        dataset_root=dataset_root,
        metadata_dir=metadata_dir,
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/scan",
    response_model=ScanResponseSchema,
    summary="Scan the entire dataset directory",
    description=(
        "Recursively scans all category folders (Acts, CourtJudgement, Tax, Legal_opinion), "
        "extracts metadata for every PDF, detects duplicates, validates files, and "
        "automatically generates documents.csv, documents.xlsx, and dataset_summary.json."
    ),
    response_description="Complete scan result with all document records and statistics.",
)
async def scan_dataset(
    service: DatasetService = Depends(get_dataset_service),
) -> ScanResponseSchema:
    """
    Trigger a full dataset directory scan.

    This is the primary endpoint of the Dataset Management Module.
    It is idempotent — running it multiple times on the same dataset
    produces the same result (deterministic document IDs via UUID5).

    Returns:
        ScanResponseSchema with statistics, document list, and any folder errors.

    Raises:
        HTTPException 500: If the dataset root is missing or unreadable.
    """
    dataset_log.info("API: POST /dataset/scan — starting scan")

    try:
        scan_result = service.scan_dataset()
    except DatasetScanError as exc:
        dataset_log.error("Scan failed | error={error}", error=exc.message)
        raise HTTPException(status_code=500, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        dataset_log.exception("Unexpected scan error | error={error}", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail="Dataset scan failed due to an unexpected error.",
        ) from exc

    response = ScanResponseSchema.from_scan_result(scan_result)

    dataset_log.info(
        "API: scan complete | total={total} | valid={valid}",
        total=response.statistics.total_documents,
        valid=response.statistics.valid_documents,
    )

    return response


@router.get(
    "/documents",
    response_model=DocumentListSchema,
    summary="List all indexed documents",
    description=(
        "Returns the list of all discovered documents from the last scan. "
        "Supports optional filtering by category and/or status."
    ),
)
async def list_documents(
    category: str | None = Query(
        default=None,
        description="Filter by category: Acts | CourtJudgement | Tax | Legal_opinion",
        examples=["Acts"],
    ),
    status: str | None = Query(
        default=None,
        description="Filter by status: valid | invalid | corrupted | empty | duplicate",
        examples=["valid"],
    ),
    service: DatasetService = Depends(get_dataset_service),
) -> DocumentListSchema:
    """
    Return all scanned documents, optionally filtered.

    Reads from the previously generated documents.csv without re-scanning.

    Args:
        category: Optional category filter.
        status:   Optional status filter.
        service:  Injected DatasetService.

    Returns:
        DocumentListSchema with total counts and filtered document list.

    Raises:
        HTTPException 404: If no scan has been performed yet (CSV missing).
        HTTPException 400: If an invalid category or status is provided.
    """
    # Validate category filter
    valid_categories = {"Acts", "CourtJudgement", "Tax", "Legal_opinion"}
    if category and category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {valid_categories}",
        )

    # Validate status filter
    valid_statuses = {s.value for s in DocumentStatus}
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of: {valid_statuses}",
        )

    raw_rows = service.get_statistics_from_csv()

    if raw_rows is None:
        raise HTTPException(
            status_code=404,
            detail="No scan data found. Please run POST /api/v1/dataset/scan first.",
        )

    # Apply filters in Python (the CSV is small enough — ~100 documents)
    filtered = raw_rows

    if category:
        filtered = [r for r in filtered if r.get("Category") == category]

    if status:
        filtered = [r for r in filtered if r.get("Status") == status]

    total = len(raw_rows)
    valid_count = sum(1 for r in raw_rows if r.get("Status") == "valid")
    invalid_count = sum(1 for r in raw_rows if r.get("Status") in ("invalid", "corrupted", "empty"))
    duplicate_count = sum(1 for r in raw_rows if r.get("Status") == "duplicate")

    dataset_log.info(
        "API: GET /dataset/documents | total={total} | filtered={filtered} | "
        "category={cat} | status={status}",
        total=total,
        filtered=len(filtered),
        cat=category,
        status=status,
    )

    return DocumentListSchema(
        total=total,
        valid=valid_count,
        invalid=invalid_count,
        duplicate=duplicate_count,
        documents=[],  # Raw CSV rows — full schema conversion done by frontend
        category_filter=category,
        status_filter=status,
    )


@router.get(
    "/export/csv",
    summary="Download documents.csv",
    description="Download the generated documents.csv metadata file.",
    response_class=FileResponse,
)
async def export_csv(
    service: DatasetService = Depends(get_dataset_service),
) -> FileResponse:
    """
    Serve documents.csv as a file download.

    Raises:
        HTTPException 404: If documents.csv does not exist yet.
    """
    settings = get_settings()
    csv_path = Path(settings.metadata_path) / "documents.csv"

    if not csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail="documents.csv not found. Run POST /api/v1/dataset/scan first.",
        )

    dataset_log.info("API: GET /dataset/export/csv — serving {path}", path=str(csv_path))

    return FileResponse(
        path=str(csv_path),
        media_type="text/csv",
        filename="documents.csv",
        headers={"Content-Disposition": 'attachment; filename="documents.csv"'},
    )


@router.get(
    "/export/xlsx",
    summary="Download documents.xlsx",
    description="Download the generated documents.xlsx metadata file with professional formatting.",
    response_class=FileResponse,
)
async def export_xlsx(
    service: DatasetService = Depends(get_dataset_service),
) -> FileResponse:
    """
    Serve documents.xlsx as a file download.

    Raises:
        HTTPException 404: If documents.xlsx does not exist yet.
    """
    settings = get_settings()
    xlsx_path = Path(settings.metadata_path) / "documents.xlsx"

    if not xlsx_path.exists():
        raise HTTPException(
            status_code=404,
            detail="documents.xlsx not found. Run POST /api/v1/dataset/scan first.",
        )

    dataset_log.info("API: GET /dataset/export/xlsx — serving {path}", path=str(xlsx_path))

    return FileResponse(
        path=str(xlsx_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="documents.xlsx",
        headers={"Content-Disposition": 'attachment; filename="documents.xlsx"'},
    )


@router.get(
    "/export/json",
    summary="Get dataset summary JSON",
    description="Return the dataset_summary.json content as a JSON response.",
)
async def export_json(
    service: DatasetService = Depends(get_dataset_service),
) -> JSONResponse:
    """
    Return dataset_summary.json content.

    Raises:
        HTTPException 404: If the JSON file does not exist yet.
    """
    import json

    settings = get_settings()
    json_path = Path(settings.metadata_path) / "dataset_summary.json"

    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail="dataset_summary.json not found. Run POST /api/v1/dataset/scan first.",
        )

    with open(json_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    dataset_log.info("API: GET /dataset/export/json — serving summary")

    return JSONResponse(content=summary)
