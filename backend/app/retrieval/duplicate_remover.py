"""
app/retrieval/duplicate_remover.py
=====================================
Deduplication utilities for the Hybrid Retrieval Engine.

PURPOSE:
    Removes duplicate chunks from combined vector + BM25 result lists before
    the fusion ranking step. Without deduplication, the same chunk may appear
    twice in the final context window — wasting LLM tokens and producing
    repetitive citations.

DUPLICATE DEFINITION:
    A chunk is considered a duplicate if it shares the same ``chunk_id`` as
    another chunk that has already been added to the output. If chunk_id is
    unavailable, a composite key of (document_id, page_number, chunk_index)
    is used as the deduplication key.

WHY DEDUPLICATION MATTERS:
    - Both Qdrant and Elasticsearch index the same chunks independently.
    - When a query matches a chunk both semantically and lexically, it appears
      in both result lists. The LLM context must contain UNIQUE chunks.
    - Deduplication after fusion ensures the Top-K selection yields K distinct
      chunks rather than K results with possible repetitions.

SOLID: Single Responsibility — deduplication only.
       Pure function — no state, no side effects.
"""

from __future__ import annotations

from typing import List, Set, Tuple

from app.models.document import RetrievedChunk
from app.retrieval.retrieval_logger import retrieval_log
from app.retrieval.retrieval_models import FusionCandidate


def _chunk_dedup_key(chunk: RetrievedChunk) -> str:
    """
    Return a deduplication key for a ``RetrievedChunk``.

    Primary key: ``chunk_id`` (deterministic UUID5).
    Fallback key: ``"<document_id>|<page_number>|<chunk_index>"`` when chunk_id
    is empty or not set, preventing unsafe pass-through of duplicates.

    Args:
        chunk: ``RetrievedChunk`` domain object.

    Returns:
        String key used for deduplication.
    """
    if chunk.chunk_id:
        return chunk.chunk_id
    return f"{chunk.document_id}|{chunk.page_number}|{chunk.chunk_index}"


def remove_duplicate_chunks(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    """
    Remove duplicate ``RetrievedChunk`` objects from a list.

    Preserves the first occurrence of each chunk (maintains ranking order).
    Order is preserved — the function is stable.

    Args:
        chunks: Input list (may contain duplicates across vector + BM25 results).

    Returns:
        Deduplicated list in the same order as the input.
    """
    seen: Set[str] = set()
    unique: List[RetrievedChunk] = []
    removed = 0

    for chunk in chunks:
        key = _chunk_dedup_key(chunk)
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
        else:
            removed += 1

    if removed:
        retrieval_log.info(
            "Duplicate chunks removed | input={n} | unique={u} | removed={r}",
            n=len(chunks),
            u=len(unique),
            r=removed,
        )
    return unique


def _candidate_dedup_key(candidate: FusionCandidate) -> str:
    """
    Return a deduplication key for a ``FusionCandidate``.

    Args:
        candidate: ``FusionCandidate`` object from the fusion step.

    Returns:
        String deduplication key.
    """
    if candidate.chunk_id:
        return candidate.chunk_id
    return f"{candidate.document_id}|{candidate.page_number}|{candidate.chunk_index}"


def remove_duplicate_candidates(
    candidates: List[FusionCandidate],
) -> List[FusionCandidate]:
    """
    Remove duplicate ``FusionCandidate`` objects from a list.

    Called after building the initial candidate pool from both retrievers
    but before applying the Weighted Rank Fusion algorithm.

    Args:
        candidates: List of fusion candidates (may include duplicates).

    Returns:
        Deduplicated list.
    """
    seen: Set[str] = set()
    unique: List[FusionCandidate] = []
    removed = 0

    for cand in candidates:
        key = _candidate_dedup_key(cand)
        if key not in seen:
            seen.add(key)
            unique.append(cand)
        else:
            removed += 1

    if removed:
        retrieval_log.info(
            "Duplicate candidates removed | input={n} | unique={u} | removed={r}",
            n=len(candidates),
            u=len(unique),
            r=removed,
        )
    return unique
