"""
app/pdf_parser/__init__.py
===========================
PDF Parser Module public interface.
"""

from app.pdf_parser.parser_controller import router as parser_router
from app.pdf_parser.parser_models import ParsedDocument, ParsedPage
from app.pdf_parser.parser_repository import (
    FileSystemParserRepository,
    ParserRepository,
)
from app.pdf_parser.parser_service import PDFParserService

__all__ = [
    "parser_router",
    "ParsedPage",
    "ParsedDocument",
    "ParserRepository",
    "FileSystemParserRepository",
    "PDFParserService",
]
