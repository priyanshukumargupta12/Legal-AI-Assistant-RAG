"""
app/pdf_parser/parser_models.py
================================
Pure Python domain models for the PDF Parsing Module.

PURPOSE:
    Defines the domain entities for parsed document pages and complete
    parsed documents. These models contain only Python standard types.

ENTITIES:
    ParsedPage      — raw text and metadata of a single PDF page
    ParsedDocument  — collection of ParsedPage objects with document metadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class ParsedPage:
    """
    Metadata and raw text extracted from a single PDF page.

    Attributes:
        document_id:          Unique UUID matching parent DocumentRecord.
        document_name:        Original PDF filename.
        category:             Document category (Acts, CourtJudgement, Tax, Legal_opinion).
        page_number:          1-based page number.
        text:                 Raw text extracted from this page.
        file_path:            Absolute path to the source file.
        source:               Name of the source file.
        extracted_at:         UTC Timestamp of extraction.
    """

    document_id: str
    document_name: str
    category: str
    page_number: int
    text: str
    file_path: str
    source: str
    extracted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ParsedDocument:
    """
    Representation of a fully parsed PDF document.

    Attributes:
        document_id:   Unique UUID matching DocumentRecord.
        document_name: Original PDF filename.
        category:      Document category.
        pages:         Ordered list of ParsedPage objects.
        total_pages:   Total number of pages parsed.
    """

    document_id: str
    document_name: str
    category: str
    pages: List[ParsedPage]
    total_pages: int
