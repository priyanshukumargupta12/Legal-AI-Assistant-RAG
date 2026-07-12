"""
app/llm/llm_utils.py
=====================
Input validation and formatting utilities for the LLM Module.

PURPOSE:
    Validates user queries and handles missing context scenarios to protect
    against token waste and model misuse.
"""

from __future__ import annotations

from typing import List, Optional
from app.llm.llm_logger import llm_log
from app.llm.llm_models import LLMResult
from app.retrieval.retrieval_models import FusionCandidate

# ── Limits ─────────────────────────────────────────────────────────────────────
MIN_QUERY_LENGTH = 3
MAX_QUERY_LENGTH = 2000


def validate_llm_query(query: str) -> None:
    """
    Validate the user query before sending to the LLM pipeline.

    Checks:
        1. Empty query
        2. Very short query
        3. Very long query
    """
    if not query or not query.strip():
        llm_log.warning("Validation failed: query is empty")
        raise ValueError("Query cannot be empty.")

    clean_len = len(query.strip())
    if clean_len < MIN_QUERY_LENGTH:
        llm_log.warning("Validation failed: query too short | len={len}", len=clean_len)
        raise ValueError(
            f"Query too short ({clean_len} chars). Minimum length: {MIN_QUERY_LENGTH}."
        )

    if clean_len > MAX_QUERY_LENGTH:
        llm_log.warning("Validation failed: query too long | len={len}", len=clean_len)
        raise ValueError(
            f"Query exceeds maximum allowed length of {MAX_QUERY_LENGTH} characters."
        )


def check_context_presence(chunks: List[FusionCandidate]) -> bool:
    """
    Return True if the context contains usable legal chunks.

    Returns False if context is empty.
    """
    if not chunks:
        return False
    # Check if all chunks have empty text
    non_empty = [c for c in chunks if getattr(c, "text", "").strip()]
    return len(non_empty) > 0


def get_empty_context_result() -> LLMResult:
    """
    Return the standard response when the context is insufficient.

    Specified requirement:
        "Information not found in the provided legal documents."
    """
    return LLMResult(
        answer="Information not found in the provided legal documents.",
        summary="Insufficient information available to process request.",
        citations=[],
        confidence_score=0.0,
    )
