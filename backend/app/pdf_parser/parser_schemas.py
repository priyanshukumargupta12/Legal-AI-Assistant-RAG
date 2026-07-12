"""
app/pdf_parser/parser_schemas.py
=================================
Pydantic v2 schemas for PDF Parsing Module.

PURPOSE:
    Provides validation structures and JSON serialization interfaces.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ParsedPageSchema(BaseModel):
    """API/JSON representation of a single parsed page."""

    page: int = Field(..., ge=1, description="1-based page number.")
    text: str = Field(..., description="Extracted raw text content.")


class ParsedDocumentSchema(BaseModel):
    """JSON output representation matching the objective specification."""

    document_id: str = Field(..., description="Unique document identifier.")
    document_name: str = Field(..., description="Original PDF filename.")
    category: str = Field(..., description="Document category.")
    pages: List[ParsedPageSchema] = Field(..., description="List of page contents.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "DOC001",
                "document_name": "IRS_Publication_17.pdf",
                "category": "Tax",
                "pages": [{"page": 1, "text": "This is page 1 content..."}],
            }
        }
    }


class ParserStatusSchema(BaseModel):
    """Response returned after parsing one or more PDFs."""

    document_id: str
    document_name: str
    total_pages: int
    extracted_pages: int
    elapsed_time_ms: float
    status: str
    error_message: Optional[str] = None
