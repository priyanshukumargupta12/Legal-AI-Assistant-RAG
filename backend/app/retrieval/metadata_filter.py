"""
app/retrieval/metadata_filter.py
==================================
Metadata filtering utilities for post-retrieval filtering.

PURPOSE:
    Applies structured filters to the list of ``RetrievedChunk`` or
    ``FusionCandidate`` objects returned by the retrievers.

    Filtering is applied AFTER retrieval (post-filter) to support cases where
    a pre-filter has not been applied (e.g., if Qdrant does not support a
    specific filter type). This ensures consistent filtering semantics
    regardless of which retriever is used.

WHY POST-FILTERING?
    - Pre-filters in Qdrant and Elasticsearch may behave differently.
    - Post-filtering on a standardized domain model guarantees consistency.
    - Enables future filter types (date ranges, page ranges) without changing
      the retriever implementations.

SUPPORTED FILTERS:
    - category_filter:  Exact match on the ``category`` field.
    - document_filter:  Exact match on the ``document_id`` field.
    - page_filter:      Inclusive range on ``page_number`` [min, max].

SOLID: Single Responsibility — only applies metadata filters to result lists.
       Pure functions — no state, no side effects.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.models.document import RetrievedChunk
from app.retrieval.retrieval_logger import retrieval_log
from app.retrieval.retrieval_models import FusionCandidate


def filter_retrieved_chunks(
    chunks: List[RetrievedChunk],
    category_filter: Optional[str] = None,
    document_filter: Optional[str] = None,
    page_range: Optional[Tuple[int, int]] = None,
) -> List[RetrievedChunk]:
    """
    Apply metadata filters to a list of ``RetrievedChunk`` objects.

    Filters are applied as AND conditions — all supplied filters must pass
    for a chunk to be included in the output.

    Args:
        chunks:          Input list of retrieved chunks.
        category_filter: If set, keep only chunks with this exact category.
        document_filter: If set, keep only chunks with this document_id.
        page_range:      If set, keep only chunks with page_number in [min, max].

    Returns:
        Filtered list of ``RetrievedChunk`` objects.
    """
    if not any([category_filter, document_filter, page_range]):
        return chunks

    before = len(chunks)
    filtered: List[RetrievedChunk] = []

    for chunk in chunks:
        if category_filter and chunk.category != category_filter:
            continue
        if document_filter and chunk.document_id != document_filter:
            continue
        if page_range:
            lo, hi = page_range
            if not (lo <= chunk.page_number <= hi):
                continue
        filtered.append(chunk)

    retrieval_log.info(
        "Post-filter applied | before={before} | after={after} | cat={cat} | doc={doc}",
        before=before,
        after=len(filtered),
        cat=category_filter or "all",
        doc=document_filter or "all",
    )
    return filtered


def filter_fusion_candidates(
    candidates: List[FusionCandidate],
    category_filter: Optional[str] = None,
    document_filter: Optional[str] = None,
    page_range: Optional[Tuple[int, int]] = None,
) -> List[FusionCandidate]:
    """
    Apply metadata filters to a list of ``FusionCandidate`` objects.

    Same semantics as ``filter_retrieved_chunks`` but operates on
    ``FusionCandidate`` domain objects used during fusion.

    Args:
        candidates:      Input list of fusion candidates.
        category_filter: If set, keep only candidates with this exact category.
        document_filter: If set, keep only candidates with this document_id.
        page_range:      If set, keep only candidates with page_number in [min, max].

    Returns:
        Filtered list of ``FusionCandidate`` objects.
    """
    if not any([category_filter, document_filter, page_range]):
        return candidates

    before = len(candidates)
    filtered: List[FusionCandidate] = []

    for cand in candidates:
        if category_filter and cand.category != category_filter:
            continue
        if document_filter and cand.document_id != document_filter:
            continue
        if page_range:
            lo, hi = page_range
            if not (lo <= cand.page_number <= hi):
                continue
        filtered.append(cand)

    retrieval_log.info(
        "Fusion candidate filter | before={before} | after={after}",
        before=before,
        after=len(filtered),
    )
    return filtered
