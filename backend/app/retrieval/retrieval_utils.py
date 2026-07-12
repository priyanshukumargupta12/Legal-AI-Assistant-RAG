"""
app/retrieval/retrieval_utils.py
==================================
Shared utility functions for the Hybrid Retrieval subsystem.

PURPOSE:
    General-purpose utilities: score formatting, result display helpers,
    timing decorators, and search timeout wrapper.

SOLID: Single Responsibility — only utility functions, no business logic.
"""

from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Any, Callable, Coroutine, List, Optional, TypeVar

from app.retrieval.retrieval_logger import retrieval_log
from app.retrieval.retrieval_models import FusionCandidate

T = TypeVar("T")


async def with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout_s: float,
    fallback: Optional[T] = None,
    label: str = "operation",
) -> Optional[T]:
    """
    Await a coroutine with a timeout, returning a fallback on timeout.

    Args:
        coro:      The coroutine to execute.
        timeout_s: Maximum seconds to wait.
        fallback:  Value returned on timeout (default: None).
        label:     Human-readable label for logging.

    Returns:
        The coroutine's result, or ``fallback`` if the timeout fires.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.TimeoutError:
        retrieval_log.warning(
            "Timeout on {label} after {t:.1f}s — returning fallback",
            label=label,
            t=timeout_s,
        )
        return fallback
    except Exception as exc:
        retrieval_log.error(
            "Error in {label} | error={err}", label=label, err=str(exc)
        )
        raise


def format_score(score: float, precision: int = 4) -> float:
    """Round a score to the given number of decimal places."""
    return round(score, precision)


def truncate_text(text: str, max_chars: int = 300) -> str:
    """
    Truncate a text string to ``max_chars`` and append '...' if truncated.

    Args:
        text:      Full text string.
        max_chars: Maximum character count.

    Returns:
        Truncated string (with '...' suffix if truncated).
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def log_candidates_table(candidates: List[FusionCandidate], label: str = "Top Results") -> None:
    """
    Log a formatted table of fusion candidates for debugging.

    Args:
        candidates: Fusion candidates to display.
        label:      Table header label.
    """
    retrieval_log.info("-" * 70)
    retrieval_log.info("{label}:", label=label)
    retrieval_log.info(
        "{:<5} {:<12} {:<10} {:<8} {:<8} {:<8}",
        "Rank", "Chunk ID", "Category", "V-Score", "BM25", "Hybrid",
    )
    for i, cand in enumerate(candidates, 1):
        retrieval_log.info(
            "{rank:<5} {cid:<12} {cat:<10} {vs:<8.4f} {bs:<8.4f} {hs:<8.4f}",
            rank=i,
            cid=cand.chunk_id[:12] if cand.chunk_id else "N/A",
            cat=cand.category[:10],
            vs=cand.vector_score,
            bs=cand.bm25_score,
            hs=cand.hybrid_score,
        )
    retrieval_log.info("-" * 70)
