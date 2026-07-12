"""
app/api/routes/dataset.py
=========================
FastAPI routes for dataset management.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.api.dependencies.services import get_dataset_service, get_settings
from app.api.responses.standard_response import StandardResponse
from app.dataset.dataset_service import DatasetService
from app.core.config import Settings

router = APIRouter(prefix="/dataset", tags=["Dataset Management"])


@router.get(
    "/pdf",
    summary="Stream a PDF file from the dataset folder",
)
def get_pdf_file(
    category: str,
    document: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Streams a PDF by category and filename from the server's dataset folder."""
    safe_category = Path(category).name
    safe_document = Path(document).name
    pdf_path = Path(settings.dataset_root_path) / safe_category / safe_document
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=404,
            detail=f"PDF not found: {safe_category}/{safe_document}",
        )
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_document}"'},
    )




@router.get(
    "",
    response_model=StandardResponse,
    summary="Get dataset summary and statistics",
)
def get_dataset_stats(
    service: Annotated[DatasetService, Depends(get_dataset_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StandardResponse:
    """Returns total documents, category counts, and registry metadata. Triggers scan if missing."""
    summary_path = Path(settings.metadata_path) / "dataset_summary.json"

    # Trigger scan if summary does not exist
    if not summary_path.exists():
        service.scan_dataset()

    with open(summary_path, "r", encoding="utf-8") as f:
        summary_data = json.load(f)

    # Re-map standard fields
    data = {
        "total_documents": summary_data.get("total_documents", 0),
        "category_statistics": summary_data.get("categories", {}),
        "dataset_summary": {
            "valid_documents": summary_data.get("valid_documents", 0),
            "invalid_documents": summary_data.get("invalid_documents", 0),
            "duplicate_documents": summary_data.get("duplicate_documents", 0),
            "total_size_mb": summary_data.get("total_size_mb", 0.0),
        }
    }
    return StandardResponse.success(
        data=data,
        message="Dataset statistics retrieved successfully."
    )


@router.post(
    "/scan",
    response_model=StandardResponse,
    summary="Scan dataset folder",
)
def scan_dataset(
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> StandardResponse:
    """Scans the configured dataset folder and regenerates files (CSV, XLSX, JSON)."""
    scan_result = service.scan_dataset()
    data = {
        "scanned_documents": len(scan_result.documents),
        "valid_documents": len(scan_result.valid_documents),
        "failed_documents": len(scan_result.invalid_documents),
        "duplicate_documents": len(scan_result.duplicate_documents),
        "files_generated": ["documents.csv", "documents.xlsx", "dataset_summary.json"]
    }
    return StandardResponse.success(
        data=data,
        message="Dataset folder scanned successfully."
    )
