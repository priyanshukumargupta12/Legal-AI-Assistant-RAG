"""
app/retrieval/query_preprocessor.py
======================================
Query preprocessing and validation utilities.

PURPOSE:
    Cleans and validates raw user query strings before they are sent to
    vector or keyword retrievers. Ensures all retrievers receive consistent,
    well-formed input.

PREPROCESSING STEPS:
    1. Strip leading/trailing whitespace.
    2. Collapse multiple internal whitespace runs into a single space.
    3. Remove control characters (null bytes, form feeds, etc.).
    4. Normalize unicode to NFC form (handles accented legal names).
    5. Optionally lowercase for case-insensitive matching.

VALIDATION RULES:
    - Empty query → raise ValueError
    - Query < 3 chars → raise ValueError (too short to be meaningful)
    - Query > 2000 chars → raise ValueError (truncate risk)

SOLID: Single Responsibility — query cleaning and validation only.
       Pure functions — no state, no side effects.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from app.retrieval.retrieval_logger import retrieval_log

# ── Configurable thresholds ────────────────────────────────────────────────────
MIN_QUERY_LENGTH: int = 3
MAX_QUERY_LENGTH: int = 2000

# Control character pattern — matches C0 and C1 control characters except \n\t
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def preprocess_query(raw_query: str, lowercase: bool = False) -> str:
    """
    Clean and normalise a raw user query string.

    Steps applied (in order):
        1. Strip leading/trailing whitespace.
        2. Normalise unicode to NFC form.
        3. Remove control characters.
        4. Collapse multiple whitespace runs into a single space.
        5. Optionally lowercase the result.

    Args:
        raw_query:  Raw query string from the user.
        lowercase:  If True, lowercases the cleaned query.

    Returns:
        Cleaned, normalised query string.

    Raises:
        ValueError: If the query is empty after cleaning.
    """
    if not raw_query:
        raise ValueError("Query must not be empty.")

    # Step 1 — strip
    cleaned = raw_query.strip()

    # Step 2 — unicode normalisation (handles é, ü, etc. in legal names)
    cleaned = unicodedata.normalize("NFC", cleaned)

    # Step 3 — remove control characters (null bytes, form feeds, etc.)
    cleaned = _CONTROL_CHARS_PATTERN.sub("", cleaned)

    # Step 4 — collapse whitespace runs (tabs, double-spaces, etc.)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Step 5 — optional lowercase
    if lowercase:
        cleaned = cleaned.lower()

    return cleaned


def validate_query(query: str) -> None:
    """
    Validate a preprocessed query string.

    Enforces minimum and maximum length constraints.

    Args:
        query: Preprocessed query string.

    Raises:
        ValueError: If the query is empty, too short, or too long.
    """
    if not query or not query.strip():
        raise ValueError("Query is empty after preprocessing.")

    length = len(query.strip())

    if length < MIN_QUERY_LENGTH:
        raise ValueError(
            f"Query is too short ({length} chars). "
            f"Minimum required: {MIN_QUERY_LENGTH} characters."
        )

    if length > MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query is too long ({length} chars). "
            f"Maximum allowed: {MAX_QUERY_LENGTH} characters."
        )


def clean_and_validate(
    raw_query: str,
    lowercase: bool = False,
    log: bool = True,
) -> str:
    """
    Convenience function combining ``preprocess_query`` and ``validate_query``.

    Args:
        raw_query: Raw query string from user input.
        lowercase: Whether to lowercase the result.
        log:       Whether to log the preprocessing result.

    Returns:
        Validated, cleaned query string.

    Raises:
        ValueError: On empty, too-short, or too-long queries.
    """
    clean = preprocess_query(raw_query, lowercase=lowercase)
    validate_query(clean)

    if log:
        retrieval_log.info(
            "Query preprocessed | raw_len={raw} | clean_len={clean} | query={q}",
            raw=len(raw_query),
            clean=len(clean),
            q=clean[:80] + ("..." if len(clean) > 80 else ""),
        )

    return clean
