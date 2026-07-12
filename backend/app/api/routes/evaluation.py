"""
app/api/routes/evaluation.py
=============================
FastAPI routes for RAG pipeline golden set evaluations.
"""

from __future__ import annotations

import time
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.responses.standard_response import StandardResponse
from app.api.dependencies.services import get_evaluation_service
from app.evaluation.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluate", tags=["Golden Set Evaluation"])


@router.post(
    "",
    response_model=StandardResponse,
    summary="Run Golden Set Evaluation",
    description="Loads the evaluation golden set, executes hybrid search, queries the LLM, and calculates retrieval accuracy and faithfulness.",
)
async def run_evaluation(
    limit: Optional[int] = Query(default=None, description="Optional limit on number of golden set entries to run."),
    service: EvaluationService = Depends(get_evaluation_service),
) -> StandardResponse:
    """
    Triggers end-to-end evaluation pipeline run.
    """
    try:
        report = await service.run_evaluation(limit=limit)
        return StandardResponse.success(
            data=report,
            message="Golden Set Evaluation completed successfully."
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {exc}"
        )


@router.get(
    "/report/json",
    response_model=StandardResponse,
    summary="Get Latest Evaluation Report JSON",
    description="Returns the parsed JSON data of the last completed evaluation run.",
)
async def get_latest_report_json(
    service: EvaluationService = Depends(get_evaluation_service),
) -> StandardResponse:
    """
    Returns the latest evaluation report details.
    """
    report = service.get_latest_report()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No evaluation report found. Please run an evaluation first."
        )
    return StandardResponse.success(
        data=report,
        message="Latest evaluation report retrieved successfully."
    )


@router.get(
    "/report/csv",
    summary="Download Evaluation CSV Report",
    description="Serves the evaluation_report.csv file for download.",
    response_class=FileResponse,
)
async def download_report_csv(
    service: EvaluationService = Depends(get_evaluation_service),
) -> FileResponse:
    """
    Returns evaluation_report.csv as file attachment.
    """
    path = service.get_report_csv_path()
    if not path or not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Evaluation CSV report not found. Run evaluation first."
        )
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename="evaluation_report.csv",
        headers={"Content-Disposition": 'attachment; filename="evaluation_report.csv"'},
    )


@router.get(
    "/report/xlsx",
    summary="Download Evaluation Excel Report",
    description="Serves the evaluation_report.xlsx file for download.",
    response_class=FileResponse,
)
async def download_report_xlsx(
    service: EvaluationService = Depends(get_evaluation_service),
) -> FileResponse:
    """
    Returns evaluation_report.xlsx as file attachment.
    """
    path = service.get_report_xlsx_path()
    if not path or not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Evaluation Excel report not found. Run evaluation first."
        )
    return FileResponse(
        path=str(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="evaluation_report.xlsx",
        headers={"Content-Disposition": 'attachment; filename="evaluation_report.xlsx"'},
    )
