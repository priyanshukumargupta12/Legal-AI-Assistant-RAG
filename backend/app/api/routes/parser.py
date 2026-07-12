"""
app/api/routes/parser.py
=========================
FastAPI routes for PDF parser orchestration.
"""

from __future__ import annotations

import time
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from app.api.dependencies.services import get_parser_service
from app.api.responses.standard_response import StandardResponse
from app.pdf_parser.parser_service import PDFParserService
from app.pdf_parser.parser_logger import parser_log

router = APIRouter(prefix="/parser", tags=["PDF Parsing"])


@router.post(
    "/parse",
    response_model=StandardResponse,
    summary="Parse all registered PDF documents page-by-page",
)
async def parse_all_documents(
    service: Annotated[PDFParserService, Depends(get_parser_service)],
    limit: Optional[int] = Query(default=None, description="Optional limit on count of documents parsed (for quick testing)"),
) -> StandardResponse:
    """
    Scans the registry CSV, parses all unparsed/registered PDF documents page-by-page,
    and extracts text into standardized page JSON outputs.
    """
    start_time = time.perf_counter()

    # Load registry records
    records = service._repository.load_registry_csv(service._registry_csv_path)
    if limit is not None:
        records = records[:limit]

    parsed_docs = []
    failed_docs = []

    for record in records:
        doc_id = str(record.get("Document_ID"))
        doc_name = record.get("File_Name")
        try:
            parsed_doc, _ = service.parse_document(doc_id)
            parsed_docs.append({
                "document_id": doc_id,
                "document_name": doc_name,
                "pages": parsed_doc.total_pages
            })
        except Exception as exc:
            parser_log.error("Failed to parse document | id={id} | error={err}", id=doc_id, err=str(exc))
            failed_docs.append({
                "document_id": doc_id,
                "document_name": doc_name,
                "error": str(exc)
            })

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    data = {
        "parsed_count": len(parsed_docs),
        "failed_count": len(failed_docs),
        "parsed_details": parsed_docs,
        "failed_details": failed_docs,
        "elapsed_time_ms": elapsed_ms
    }

    return StandardResponse.success(
        data=data,
        message=f"PDF parsing complete. Parsed {len(parsed_docs)} documents successfully."
    )
