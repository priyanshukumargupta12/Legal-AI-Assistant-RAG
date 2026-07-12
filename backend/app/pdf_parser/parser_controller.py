"""
app/pdf_parser/parser_controller.py
====================================
HTTP controller for the PDF Parsing Module.

DEPRECATION WARNING:
    This controller is legacy dead code.
    Active API routes for PDF parsing are aggregated in:
        app/api/routes/parser.py
    Refer to that module for production endpoints.
"""


from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.core.exceptions import PDFParseError, ResourceNotFoundError
from app.pdf_parser.parser_logger import parser_log
from app.pdf_parser.parser_repository import FileSystemParserRepository
from app.pdf_parser.parser_schemas import ParsedDocumentSchema, ParserStatusSchema
from app.pdf_parser.parser_service import PDFParserService

router = APIRouter(
    prefix="/parser",
    tags=["PDF Parsing"],
)


def get_parser_service() -> PDFParserService:
    """Dependency injector for PDFParserService."""
    settings = get_settings()
    csv_path = Path(settings.metadata_path) / "documents.csv"
    output_dir = Path(settings.metadata_path) / "parsed"

    repository = FileSystemParserRepository()
    return PDFParserService(
        repository=repository,
        registry_csv_path=csv_path,
        output_dir=output_dir,
    )


@router.post(
    "/parse/{document_id}",
    response_model=ParserStatusSchema,
    summary="Parse a PDF document page-by-page",
    description="Loads a PDF document from the registry by its UUID, extracts text page-by-page, generates standard LangChain Document objects, and saves a parsed JSON to metadata/parsed/.",
)
async def parse_document(
    document_id: str,
    service: PDFParserService = Depends(get_parser_service),
) -> ParserStatusSchema:
    """Trigger page-by-page parsing of a registered PDF."""
    start_time = time.perf_counter()
    try:
        parsed_doc, _ = service.parse_document(document_id)
        elapsed = (time.perf_counter() - start_time) * 1000
        return ParserStatusSchema(
            document_id=parsed_doc.document_id,
            document_name=parsed_doc.document_name,
            total_pages=parsed_doc.total_pages,
            extracted_pages=len(parsed_doc.pages),
            elapsed_time_ms=elapsed,
            status="success",
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except PDFParseError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        parser_log.exception("Unexpected error during parsing API call")
        raise HTTPException(status_code=500, detail=f"Unexpected parsing error: {exc}") from exc


@router.get(
    "/output/{document_id}",
    response_model=ParsedDocumentSchema,
    summary="Get parsed JSON of a document",
)
async def get_parsed_json(
    document_id: str,
) -> ParsedDocumentSchema:
    """Get the generated parsed JSON contents for a document."""
    settings = get_settings()
    json_path = Path(settings.metadata_path) / "parsed" / f"{document_id}.json"

    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Parsed output for document '{document_id}' not found. Run POST /parser/parse/{document_id} first.",
        )

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)
        return ParsedDocumentSchema(**data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to read parsed JSON: {exc}") from exc
