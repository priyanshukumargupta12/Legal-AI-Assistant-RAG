"""
app/golden_set/golden_utils.py
================================
Stateless utility functions for the Golden Set Management Module.

PURPOSE:
    Provides reusable, side-effect-free helper functions used by the
    importer, validator, and service layers. Contains no business logic
    or state — pure transformation and lookup functions only.

FUNCTIONS:
    detect_encoding          — detect file encoding via chardet
    normalize_column_name    — strip and lowercase for flexible matching
    build_column_mapping     — map raw CSV header → canonical column names
    sanitize_page_number     — coerce a raw value to int or None
    sanitize_text            — strip whitespace from a raw cell value
    map_source_to_dataset    — look up a source document in documents.csv
    compute_golden_record_id — generate a stable ID for a golden record

SOLID: Single Responsibility — stateless utility functions only.
DRY:   Used across csv_importer, excel_importer, validator, and service.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

from app.golden_set.golden_logger import golden_log


# =============================================================================
# ENCODING DETECTION
# =============================================================================

def detect_encoding(file_path: Path) -> str:
    """
    Detect the character encoding of a file using chardet.

    Falls back to 'utf-8' if chardet is unavailable or cannot
    determine the encoding with sufficient confidence.

    Args:
        file_path: Absolute path to the file to inspect.

    Returns:
        str: Detected encoding name (e.g., 'utf-8', 'utf-16', 'latin-1').
    """
    try:
        import chardet  # type: ignore
        with open(file_path, "rb") as f:
            raw_bytes = f.read(65536)  # Read first 64 KB for detection
        result = chardet.detect(raw_bytes)
        detected = result.get("encoding") or "utf-8"
        confidence = result.get("confidence", 0.0)
        golden_log.debug(
            "Encoding detected | file={file} | encoding={enc} | confidence={conf:.2f}",
            file=file_path.name,
            enc=detected,
            conf=confidence,
        )
        # Use utf-8 as fallback for very low confidence detections
        if confidence < 0.5:
            golden_log.warning(
                "Low confidence encoding detection ({conf:.2f}) for {file}; defaulting to utf-8",
                conf=confidence,
                file=file_path.name,
            )
            return "utf-8"
        return detected
    except ImportError:
        golden_log.warning("chardet not available; defaulting to utf-8 for {file}", file=file_path.name)
        return "utf-8"
    except Exception as exc:
        golden_log.warning("Encoding detection failed for {file}: {err}; defaulting to utf-8", file=file_path.name, err=str(exc))
        return "utf-8"


# =============================================================================
# COLUMN NORMALIZATION
# =============================================================================

# Canonical column name → list of known aliases (lowercase, stripped)
_COLUMN_ALIASES: Dict[str, List[str]] = {
    "query": ["query", "question", "q"],
    "expected_answer": [
        "expected_answer",
        "ground_truth_answer",
        "ground_truth",
        "answer",
        "expected answer",
        "ground truth answer",
        "groundtruth",
        "expected",
    ],
    "source_document": [
        "source_document",
        "source document",
        "source",
        "document",
        "relevant_doc",
        "relevant doc",
        "doc",
        "filename",
        "file",
    ],
    "page_number": [
        "page_number",
        "page number",
        "page",
        "pagenumber",
        "pg",
        "relevant_page",
        "relevant page",
    ],
    "category": ["category", "cat", "type", "doc_type", "document_type"],
    "citation": ["citation", "cite", "legal_citation", "legal citation", "reference"],
    "difficulty": ["difficulty", "level", "complexity"],
    "tags": ["tags", "tag", "keywords", "keyword", "topics"],
    "notes": ["notes", "note", "comment", "comments", "remarks"],
}


def normalize_column_name(name: str) -> str:
    """
    Normalize a raw column header to lowercase, stripped form.

    Args:
        name: Raw column header string.

    Returns:
        str: Lowercased, whitespace-stripped column name.
    """
    return name.strip().lower()


def build_column_mapping(raw_headers: List[str]) -> Dict[str, str]:
    """
    Map raw CSV/Excel column headers to canonical column names.

    Uses case-insensitive fuzzy matching against known aliases to handle
    variations like "Ground_Truth_Answer" → "expected_answer".

    Args:
        raw_headers: List of raw header strings from the source file.

    Returns:
        Dict mapping raw_header → canonical_name.
        Headers that match no canonical name are mapped to themselves.

    Example:
        >>> build_column_mapping(["Query", "Ground_Truth_Answer", "Source_Document"])
        {"Query": "query", "Ground_Truth_Answer": "expected_answer", "Source_Document": "source_document"}
    """
    mapping: Dict[str, str] = {}
    for raw in raw_headers:
        normalized = normalize_column_name(raw)
        matched = False
        for canonical, aliases in _COLUMN_ALIASES.items():
            if normalized in aliases:
                mapping[raw] = canonical
                matched = True
                break
        if not matched:
            mapping[raw] = normalized  # keep as-is if unrecognized
    return mapping


# =============================================================================
# FIELD SANITIZATION
# =============================================================================

def sanitize_text(value: Optional[object]) -> Optional[str]:
    """
    Strip whitespace from a raw cell value, returning None for empty cells.

    Args:
        value: Raw cell value (any type from pandas/openpyxl).

    Returns:
        Stripped string, or None if the value is null or empty.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def sanitize_page_number(value: Optional[object]) -> Optional[int]:
    """
    Coerce a raw page number value to a positive integer.

    Handles common representations:
        "15"   → 15
        "15.0" → 15
        "Page 15" → None (cannot parse "Page 15" reliably)
        ""     → None
        None   → None

    Args:
        value: Raw cell value (any type).

    Returns:
        Positive int if parseable, otherwise None.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(float(text))
        return parsed if parsed > 0 else None
    except (ValueError, TypeError):
        return None


# =============================================================================
# SOURCE DOCUMENT MAPPING
# =============================================================================

def map_source_to_dataset(
    source_document: str,
    documents_csv_path: Path,
) -> Dict[str, Optional[object]]:
    """
    Look up a source document filename in documents.csv.

    Performs a case-insensitive filename match against the 'file_name'
    column in documents.csv. Returns metadata fields if found.

    Args:
        source_document:     Filename to look up (e.g., "Title26_Vol2.pdf").
        documents_csv_path:  Absolute path to documents.csv.

    Returns:
        Dict with keys: document_id, category, page_count, is_indexed.
        All fields are None and is_indexed=False if the document is not found.
    """
    result: Dict[str, Optional[object]] = {
        "document_id": None,
        "category": None,
        "page_count": None,
        "is_indexed": False,
    }

    if not documents_csv_path.exists():
        golden_log.warning(
            "documents.csv not found at {path}; source mapping unavailable",
            path=str(documents_csv_path),
        )
        return result

    source_lower = source_document.strip().lower()

    try:
        with open(documents_csv_path, "r", encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                file_name = row.get("file_name", "") or ""
                if file_name.strip().lower() == source_lower:
                    result["document_id"] = row.get("document_id") or None
                    result["category"] = row.get("category") or None
                    page_str = row.get("page_count", "") or ""
                    try:
                        result["page_count"] = int(page_str) if page_str.strip() else None
                    except ValueError:
                        result["page_count"] = None
                    result["is_indexed"] = True
                    break
    except Exception as exc:
        golden_log.error(
            "Failed to read documents.csv for source mapping | error={err}",
            err=str(exc),
        )

    return result


# =============================================================================
# GOLDEN RECORD ID
# =============================================================================

def compute_golden_record_id(query: str, source_document: str) -> str:
    """
    Generate a stable, deterministic short ID for a golden record.

    Uses SHA256 of (lowercased query + source_document) truncated to 12 hex chars.
    Used for deduplication cross-referencing in exports.

    Args:
        query:           The query string.
        source_document: The source document filename.

    Returns:
        12-character hex string (e.g., "a3f0c2e1b9d4").
    """
    content = f"{query.strip().lower()}|{source_document.strip().lower()}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
