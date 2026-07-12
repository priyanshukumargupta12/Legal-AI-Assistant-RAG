"""
app/pdf_parser/parser_utils.py
================================
Stateless utilities for PDF text extraction.

PURPOSE:
    Provides helper functions for PyMuPDF extraction, password checking,
    text decoding, and clean conversions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import fitz  # PyMuPDF

from app.core.exceptions import PDFParseError


def verify_pdf_accessible(file_path: Path) -> Tuple[bool, str]:
    """
    Check if the PDF exists and is not encrypted/password-protected.

    Args:
        file_path: Path to the file.

    Returns:
        Tuple of (is_accessible: bool, error_message: str)
    """
    if not file_path.exists():
        return False, "File does not exist."

    try:
        doc = fitz.open(str(file_path))
        is_encrypted = doc.is_encrypted
        doc.close()
        if is_encrypted:
            return False, "PDF is password-protected."
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"Failed to open/read PDF structure: {exc}"


def clean_extracted_text(text: str) -> str:
    """
    Perform light sanitization of extracted page text.

    Removes null bytes and strips leading/trailing spaces.

    Args:
        text: Extracted raw text.

    Returns:
        Sanitized text.
    """
    if not text:
        return ""
    # Remove null bytes which can crash databases or files
    cleaned = text.replace("\x00", "")
    return cleaned.strip()
