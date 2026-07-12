"""
app/embeddings/embedding_utils.py
=================================
Validation and helper functions for the Embedding Module.

PURPOSE:
    Provides validation functions for document chunks before sending them
    to the embedding model or saving to Qdrant. Ensures compliance with
    production requirements:
    - No empty chunk text
    - Correct embedding dimensions
    - No duplicate chunk IDs
    - No missing required metadata fields
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


def validate_chunk_metadata(chunk: Dict[str, Any]) -> List[str]:
    """
    Validate that the chunk contains all required metadata and top-level fields.

    Returns:
        List of validation error strings. Empty if valid.
    """
    errors = []

    # 1. Validate top-level fields
    required_fields = ["chunk_id", "document_id", "document_name", "category", "text"]
    for field in required_fields:
        val = chunk.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing or empty required field: '{field}'")

    # Handle page number (could be named "page" or "page_number" at top level)
    page_num = chunk.get("page") or chunk.get("page_number")
    if page_num is None:
        errors.append("Missing page number ('page' or 'page_number')")
    elif not isinstance(page_num, int) or page_num < 1:
        errors.append(f"Invalid page number: {page_num}. Must be >= 1.")

    # 2. Validate empty chunk text
    text = chunk.get("text", "")
    if text is not None and not str(text).strip():
        errors.append("Chunk text content is empty or whitespace-only.")

    # 3. Validate metadata dictionary
    metadata = chunk.get("metadata")
    if metadata is None:
        errors.append("Missing 'metadata' dictionary field.")
    elif not isinstance(metadata, dict):
        errors.append("'metadata' field must be a dictionary.")
    else:
        # Check required fields inside metadata
        required_metadata_fields = ["document_id", "document_name", "category", "page_number"]
        for field in required_metadata_fields:
            if field not in metadata or metadata[field] is None:
                errors.append(f"Missing required key in metadata dict: '{field}'")

    return errors


def validate_embedding_dimension(embedding: List[float], expected_dim: int = 384) -> bool:
    """
    Validate that the generated embedding vector has the expected dimension.

    Args:
        embedding: Vector list.
        expected_dim: Expected length of vector (384 for bge-small-en-v1.5).

    Returns:
        True if dimensions are correct, False otherwise.
    """
    return len(embedding) == expected_dim


def detect_duplicates(chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    Scan a list of chunks and filter out any with duplicate chunk_id values.

    Args:
        chunks: List of chunk dictionaries.

    Returns:
        Tuple of (filtered_chunks_list, set_of_duplicate_chunk_ids)
    """
    seen_ids: Set[str] = set()
    duplicates: Set[str] = set()
    filtered: List[Dict[str, Any]] = []

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if not chunk_id:
            filtered.append(chunk)
            continue

        if chunk_id in seen_ids:
            duplicates.add(chunk_id)
        else:
            seen_ids.add(chunk_id)
            filtered.append(chunk)

    return filtered, duplicates
