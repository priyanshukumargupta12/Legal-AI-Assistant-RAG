"""
app/elasticsearch/elastic_utils.py
=====================================
Validation and pre-processing utilities for the Elasticsearch pipeline.

PURPOSE:
    Pure functions that validate and transform ``DocumentChunk`` objects
    before they are indexed. Keeps validation logic out of the service layer.

DESIGN:
    - All functions are stateless and side-effect free (pure functions).
    - Returns structured validation results — never silently drops data.
    - Raises ValueError only for unrecoverable data issues.

SOLID: Single Responsibility — only data validation / transformation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.elasticsearch.elastic_logger import elastic_log
from app.elasticsearch.elastic_models import ElasticsearchDocument
from app.models.document import DocumentChunk

# ── Valid category values ──────────────────────────────────────────────────────
VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        "Acts",
        "CourtJudgement",
        "Tax",
        "Legal_opinion",
        "Regulations",
        "Other",
    }
)


def validate_chunk(chunk: DocumentChunk) -> Tuple[bool, Optional[str]]:
    """
    Validate a single ``DocumentChunk`` before indexing.

    Checks performed:
        1. Non-empty ``chunk_id``.
        2. Non-empty ``document_id``.
        3. Non-empty ``text`` (after stripping whitespace).
        4. ``text`` length >= 10 characters.
        5. Non-empty ``document_name``.
        6. Non-empty ``category``.

    Args:
        chunk: The ``DocumentChunk`` domain object to validate.

    Returns:
        (True, None) if valid.
        (False, reason) if invalid, where ``reason`` is a description string.
    """
    if not chunk.chunk_id:
        return False, "chunk_id is empty"
    if not chunk.document_id:
        return False, "document_id is empty"
    if not chunk.text or not chunk.text.strip():
        return False, "chunk text is empty"
    if len(chunk.text.strip()) < 10:
        return False, f"chunk text too short ({len(chunk.text.strip())} chars)"
    if not chunk.document_name:
        return False, "document_name is missing"
    if not chunk.category:
        return False, "category is missing"
    return True, None


def validate_chunks_batch(
    chunks: List[DocumentChunk],
) -> Tuple[List[DocumentChunk], List[Dict[str, Any]]]:
    """
    Validate a batch of chunks and separate valid from invalid ones.

    Args:
        chunks: Raw list of ``DocumentChunk`` objects.

    Returns:
        Tuple of:
            - valid_chunks: Chunks that passed all validation checks.
            - invalid_records: List of dicts describing invalid chunks.
    """
    valid: List[DocumentChunk] = []
    invalid: List[Dict[str, Any]] = []

    for chunk in chunks:
        ok, reason = validate_chunk(chunk)
        if ok:
            valid.append(chunk)
        else:
            invalid.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "reason": reason,
                }
            )
            elastic_log.warning(
                "Chunk failed validation | chunk_id={cid} | reason={reason}",
                cid=chunk.chunk_id,
                reason=reason,
            )

    return valid, invalid


def detect_duplicate_chunk_ids(chunks: List[DocumentChunk]) -> List[str]:
    """
    Detect duplicate chunk_id values within a batch.

    In Elasticsearch, indexing a document with an existing ``_id`` will
    silently overwrite it (upsert). This function is used to log warnings
    when duplicates are found so operators can investigate.

    Args:
        chunks: List of chunks to inspect.

    Returns:
        List of duplicate chunk_id strings.
    """
    seen: set[str] = set()
    duplicates: List[str] = []
    for chunk in chunks:
        if chunk.chunk_id in seen:
            duplicates.append(chunk.chunk_id)
        else:
            seen.add(chunk.chunk_id)
    return duplicates


def chunk_to_es_document(chunk: DocumentChunk) -> ElasticsearchDocument:
    """
    Convert a ``DocumentChunk`` domain object to an ``ElasticsearchDocument``.

    Applies light text cleaning:
        - Collapse runs of whitespace in chunk_text.
        - Strip leading/trailing whitespace.

    Args:
        chunk: Validated ``DocumentChunk``.

    Returns:
        ``ElasticsearchDocument`` ready for bulk indexing.
    """
    clean_text = re.sub(r"\s+", " ", chunk.text).strip()
    return ElasticsearchDocument(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_name=chunk.document_name,
        category=chunk.category,
        page_number=chunk.page_number,
        chunk_index=chunk.chunk_index,
        chunk_text=clean_text,
        source="keyword",
        metadata=dict(chunk.metadata) if chunk.metadata else {},
    )


def build_bulk_actions(
    documents: List[ElasticsearchDocument],
    index_name: str,
) -> List[Dict[str, Any]]:
    """
    Build the list of bulk action dicts for the Elasticsearch helpers.bulk() API.

    Each action is a two-element sequence:
        { "_index": ..., "_id": ..., "_source": ... }

    Using chunk_id as ``_id`` ensures idempotent upserts — re-indexing a
    document that already exists in ES simply overwrites it without errors.

    Args:
        documents: List of ``ElasticsearchDocument`` objects.
        index_name: Target Elasticsearch index name.

    Returns:
        List of bulk action dicts.
    """
    actions: List[Dict[str, Any]] = []
    for doc in documents:
        actions.append(
            {
                "_index": index_name,
                "_id": doc.chunk_id,  # idempotent upsert key
                "_source": {
                    "chunk_id": doc.chunk_id,
                    "document_id": doc.document_id,
                    "document_name": doc.document_name,
                    "category": doc.category,
                    "page_number": doc.page_number,
                    "chunk_index": doc.chunk_index,
                    "chunk_text": doc.chunk_text,
                    "source": doc.source,
                    "indexed_at": doc.indexed_at,
                    "metadata": doc.metadata,
                },
            }
        )
    return actions
