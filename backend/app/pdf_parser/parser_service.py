"""
app/pdf_parser/parser_service.py
=================================
Service layer orchestrating the PDF Parsing logic.

PURPOSE:
    Loads a PDF file page-by-page, extracts text, converts pages to LangChain
    Document objects, validates extracted pages, and exports structured JSONs.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF
from langchain_core.documents import Document

from app.core.exceptions import PDFParseError, ResourceNotFoundError
from app.pdf_parser.parser_logger import parser_log
from app.pdf_parser.parser_models import ParsedDocument, ParsedPage
from app.pdf_parser.parser_repository import ParserRepository
from app.pdf_parser.parser_utils import clean_extracted_text, verify_pdf_accessible


class PDFParserService:
    """
    Orchestrates the page-by-page PDF parsing use case.
    """

    def __init__(
        self,
        repository: ParserRepository,
        registry_csv_path: Path,
        output_dir: Path,
    ) -> None:
        self._repository = repository
        self._registry_csv_path = registry_csv_path
        self._output_dir = output_dir

    def parse_document(self, document_id: str) -> Tuple[ParsedDocument, List[Document]]:
        """
        Locate a document in the registry, parse it page-by-page,
        generate domain objects and LangChain Documents, and export the JSON.

        Args:
            document_id: UUID of the document in registry.

        Returns:
            Tuple of (ParsedDocument, List[Document] as LangChain Documents).
        """
        # Find document in registry
        records = self._repository.load_registry_csv(self._registry_csv_path)
        matching = [r for r in records if str(r.get("Document_ID")) == document_id]
        if not matching:
            raise ResourceNotFoundError(
                resource_type="Document",
                identifier=document_id,
            )

        doc_record = matching[0]
        file_path = Path(doc_record["File_Path"])
        category = doc_record["Category"]
        file_name = doc_record["File_Name"]

        parser_log.info(
            "Parsing started | file={file} | id={id}",
            file=file_name,
            id=document_id,
        )

        start_time = time.perf_counter()

        # Check accessibility
        accessible, error_msg = verify_pdf_accessible(file_path)
        if not accessible:
            parser_log.error(
                "PDF inaccessible | file={file} | error={error}",
                file=file_name,
                error=error_msg,
            )
            raise PDFParseError(message=error_msg, file_path=str(file_path))

        parsed_pages: List[ParsedPage] = []
        langchain_docs: List[Document] = []

        try:
            doc = fitz.open(str(file_path))
            total_pages = len(doc)

            for idx, page in enumerate(doc):
                page_num = idx + 1
                raw_text = page.get_text()
                text = clean_extracted_text(raw_text)

                # Warn if page is empty (contains no text)
                if not text:
                    parser_log.warning(
                        "Empty page | file={file} | page={page}",
                        file=file_name,
                        page=page_num,
                    )

                # Domain entity page
                parsed_page = ParsedPage(
                    document_id=document_id,
                    document_name=file_name,
                    category=category,
                    page_number=page_num,
                    text=text,
                    file_path=str(file_path),
                    source=file_name,
                    extracted_at=datetime.now(tz=timezone.utc),
                )
                parsed_pages.append(parsed_page)

                # LangChain Document
                lc_doc = Document(
                    page_content=text,
                    metadata={
                        "document_id": document_id,
                        "document_name": file_name,
                        "page_number": page_num,
                        "category": category,
                        "file_path": str(file_path),
                    },
                )
                langchain_docs.append(lc_doc)

                parser_log.debug(
                    "Page extracted | file={file} | page={page}/{total}",
                    file=file_name,
                    page=page_num,
                    total=total_pages,
                )

            doc.close()

        except Exception as exc:  # noqa: BLE001
            parser_log.error(
                "Parser exception | file={file} | error={error}",
                file=file_name,
                error=str(exc),
            )
            raise PDFParseError(
                message=f"Parser failed during extraction: {exc}",
                file_path=str(file_path),
            ) from exc

        parsed_document = ParsedDocument(
            document_id=document_id,
            document_name=file_name,
            category=category,
            pages=parsed_pages,
            total_pages=len(parsed_pages),
        )

        # Write parsed document JSON output
        output_json_path = self._output_dir / f"{document_id}.json"
        self._repository.save_parsed_json(parsed_document, output_json_path)

        elapsed = (time.perf_counter() - start_time) * 1000
        parser_log.info(
            "Parsing success | file={file} | pages={pages} | elapsed={elapsed:.2f}ms",
            file=file_name,
            pages=len(parsed_pages),
            elapsed=elapsed,
        )

        return parsed_document, langchain_docs
