"""
app/chunking/chunk_utils.py
============================
Stateless utility functions for the Intelligent Chunking Module.

PURPOSE:
    Provides pure functions with no side effects for:
        - Generating deterministic chunk IDs
        - Estimating token counts from character counts
        - Validating chunk text content
        - Validating chunk metadata completeness
        - Building the RecursiveCharacterTextSplitter instance

    All functions are small, single-purpose, and trivially unit-testable
    without any mocking or dependency injection.

WHY RecursiveCharacterTextSplitter?
    Legal documents have rich hierarchical structure: paragraphs, sentences,
    and dense tables. RecursiveCharacterTextSplitter tries a prioritized list
    of separators in order, falling back to coarser splits only when needed:

        Priority 1: \\n\\n  — Paragraph boundaries (most semantically clean)
        Priority 2: . \\s  — Sentence boundaries (preserves meaning units)
        Priority 3: \\n    — Line boundaries (useful for table rows, lists)
        Priority 4: \\s    — Word boundaries (last resort before char split)
        Priority 5: ""    — Character-level split (emergency fallback only)

    This strategy produces chunks that respect semantic boundaries as much as
    possible, which directly improves vector similarity and BM25 retrieval.

WHY 100-CHARACTER OVERLAP?
    Retrieval depends on every chunk being self-contained enough to answer
    a legal question. Without overlap, information split across a chunk
    boundary is lost. 100 characters (~25 tokens) provides a "safety margin"
    so that:
        - Sentence fragments at chunk edges are repeated in both chunks
        - Cross-chunk references (e.g., "as stated above, § 523(a)...") appear
          in the new chunk's context window

WHY 500 CHARACTERS PER CHUNK?
    At ~4 chars/token, 500 chars ≈ 125 tokens. This is small enough to
    keep embedding granularity high (precise retrieval) while large enough
    to contain a complete legal sub-provision or reasoning sentence.

SOLID: Single Responsibility — only provides pure utility functions.
DRY:   Every utility defined once here; never inline-duplicated in services.
"""

from __future__ import annotations

import re
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter


# ─── Constants ────────────────────────────────────────────────────────────────

#: Target chunk size in characters (≈ 125 tokens at 4 chars/token).
CHUNK_SIZE: int = 500

#: Number of overlapping characters between consecutive chunks (≈ 25 tokens).
CHUNK_OVERLAP: int = 100

#: Separator priority list — tried in order by RecursiveCharacterTextSplitter.
#: Paragraph → Sentence → Line → Word → Character.
CHUNK_SEPARATORS: List[str] = ["\n\n", ". ", "\n", " ", ""]

#: Minimum character length; chunks shorter than this are discarded.
MIN_CHUNK_LENGTH: int = 20

#: Token estimation ratio: 1 token ≈ 4 characters (GPT-4 standard).
CHARS_PER_TOKEN: int = 4

#: Required keys that must be present in every LangChain Document's metadata.
REQUIRED_METADATA_KEYS: tuple[str, ...] = (
    "document_id",
    "document_name",
    "category",
    "file_path",
    "page_number",
)


# ─── Splitter Factory ─────────────────────────────────────────────────────────

def build_text_splitter(
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    separators: List[str] | None = None,
) -> RecursiveCharacterTextSplitter:
    """
    Construct a configured RecursiveCharacterTextSplitter instance.

    Using a factory function enables Dependency Injection — callers can
    override chunk_size, chunk_overlap, and separators without modifying
    the service class. This also supports future parallel processing where
    each worker thread needs its own splitter instance.

    Args:
        chunk_size:    Target chunk character length. Defaults to 500.
        chunk_overlap: Overlap character count between chunks. Defaults to 100.
        separators:    Ordered separator list. Defaults to paragraph/sentence/line/word/char.

    Returns:
        Configured RecursiveCharacterTextSplitter instance.

    Example:
        >>> splitter = build_text_splitter()
        >>> chunks = splitter.split_text("Long legal text here...")
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators or CHUNK_SEPARATORS,
        keep_separator=True,
        length_function=len,
        is_separator_regex=False,
    )


#  Chunk ID Generation 

def generate_chunk_id(
    document_id: str,
    page_number: int,
    chunk_index: int,
) -> str:
    """
    Generate a globally unique and deterministic chunk identifier.

    Format: <doc_prefix>_PAGE<PPP>_CHUNK<CCC>

    The doc_prefix is derived from the document UUID — either the first
    segment of a hyphenated UUID or the first 8 characters of a plain ID.
    Page and chunk numbers are zero-padded to 3 digits for stable sorting.

    WHY DETERMINISTIC IDs?
        Reproducibility: re-running the chunker on the same document always
        produces the same IDs. This allows safe re-ingestion into Qdrant and
        Elasticsearch without creating phantom duplicates.

    Args:
        document_id:  UUID string of the parent document.
        page_number:  1-based page number (padded to 3 digits).
        chunk_index:  0-based chunk index within the page (padded to 3 digits).

    Returns:
        Structured chunk ID string.

    Example:
        >>> generate_chunk_id("1808ca0c-57c1-517c-9af0", 15, 3)
        '1808ca0c_PAGE015_CHUNK003'
        >>> generate_chunk_id("DOC001", 1, 0)
        'DOC001__PAGE001_CHUNK000'
    """
    # Extract prefix: first segment of hyphenated UUID, or first 8 chars
    if "-" in document_id:
        doc_prefix = document_id.split("-")[0]
    else:
        doc_prefix = document_id[:8]

    return f"{doc_prefix}_PAGE{page_number:03d}_CHUNK{chunk_index:03d}"


# ─── Token Estimation ─────────────────────────────────────────────────────────

def estimate_token_count(text: str) -> int:
    """
    Estimate the number of LLM tokens in a text block.

    Uses the widely accepted heuristic: 1 token ≈ 4 characters for English
    text (GPT tokenizer standard). This avoids loading a full tokenizer at
    chunk time, keeping the chunker lightweight and fast.

    For more accurate estimates, a tiktoken or HuggingFace tokenizer can
    replace this function without changing the calling interface.

    Args:
        text: Input string to estimate tokens for.

    Returns:
        Estimated token count (minimum 1 for non-empty text).

    Example:
        >>> estimate_token_count("Hello world")  # 11 chars → ~3 tokens
        3
        >>> estimate_token_count("")
        0
    """
    if not text:
        return 0
    return max(1, round(len(text) / CHARS_PER_TOKEN))


# ─── Text Validation ──────────────────────────────────────────────────────────

def is_empty_chunk(text: str) -> bool:
    """
    Return True if the text is empty or contains only whitespace.

    Args:
        text: Candidate chunk text.

    Returns:
        True if the chunk should be discarded as empty.
    """
    return not text or not text.strip()


def is_too_short(text: str, min_length: int = MIN_CHUNK_LENGTH) -> bool:
    """
    Return True if the stripped text is shorter than the minimum required length.

    Very short chunks (e.g., lone page headers, single words) add noise to
    the vector store and degrade retrieval precision.

    Args:
        text:       Candidate chunk text.
        min_length: Minimum character count. Defaults to MIN_CHUNK_LENGTH (20).

    Returns:
        True if the chunk should be discarded as too short.
    """
    return len(text.strip()) < min_length


def clean_chunk_text(text: str) -> str:
    """
    Clean a raw text split before storing it as a chunk.

    Operations applied (in order):
        1. Strip leading/trailing whitespace.
        2. Collapse runs of 3+ newlines to double newlines.
        3. Collapse runs of 3+ spaces to a single space.

    Args:
        text: Raw text from RecursiveCharacterTextSplitter.

    Returns:
        Cleaned text string.
    """
    text = text.strip()
    # Collapse excessive blank lines (e.g., from PDF header/footer noise)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse excessive spaces
    text = re.sub(r" {3,}", " ", text)
    return text


# ─── Metadata Validation ──────────────────────────────────────────────────────

def validate_chunk_metadata(metadata: dict) -> List[str]:
    """
    Validate that all mandatory keys exist and contain non-null values.

    Also validates that page_number is a positive integer. Returns a list
    of human-readable error messages (empty list means valid).

    Args:
        metadata: The metadata dict from a LangChain Document.

    Returns:
        List of validation error strings. Empty if all checks pass.

    Example:
        >>> validate_chunk_metadata({"document_id": "abc", ...})
        []
        >>> validate_chunk_metadata({})
        ["Missing required metadata key: 'document_id'", ...]
    """
    errors: List[str] = []

    for key in REQUIRED_METADATA_KEYS:
        if key not in metadata or metadata[key] is None:
            errors.append(f"Missing required metadata key: '{key}'")
            continue

        # Additional type check for page_number
        if key == "page_number":
            try:
                page_val = int(metadata[key])
                if page_val < 1:
                    errors.append(
                        f"page_number must be >= 1, got: {page_val}"
                    )
            except (ValueError, TypeError):
                errors.append(
                    f"page_number must be a valid integer, got: {metadata[key]!r}"
                )

        # Validate string fields are non-empty
        elif isinstance(metadata[key], str) and not metadata[key].strip():
            errors.append(f"Metadata key '{key}' must not be an empty string.")

    return errors


def build_chunk_metadata(
    document_id: str,
    document_name: str,
    category: str,
    page_number: int,
    file_path: str,
) -> dict:
    """
    Build the canonical metadata dict to be stored with each chunk.

    WHY A DEDICATED BUILDER?
        Centralizes the metadata schema so that if a new field is added,
        only this function needs updating — not every call site.

    Args:
        document_id:   UUID string of the parent document.
        document_name: PDF filename.
        category:      Legal document category.
        page_number:   1-based page number.
        file_path:     Absolute file path to the source PDF.

    Returns:
        Dict with all required metadata keys populated.
    """
    return {
        "document_id": document_id,
        "document_name": document_name,
        "category": category,
        "page_number": page_number,
        "file_path": file_path,
        "source": document_name,
    }
