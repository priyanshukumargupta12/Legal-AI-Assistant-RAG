"""
app/chunking/chunk_schemas.py
==============================
Pydantic v2 schemas for the Intelligent Chunking Module.

PURPOSE:
    Defines validated input/output schemas for the chunking pipeline.
    Separates wire-format (JSON / API) concerns from domain entity concerns
    (chunk_models.py). Pydantic ensures all outbound data is correctly
    typed and serializable.

SCHEMA HIERARCHY:
    ChunkMetadataSchema       — Preserved metadata fields for each chunk.
    ChunkSchema               — Canonical output schema matching chunks.json format.
    ChunkDetailSchema         — Extended schema with all internal fields.
    ChunkStatisticsSchema     — Statistics summary for one document.
    GlobalChunkStatsSchema    — Cross-document batch statistics.
    ChunkingResponseSchema    — Full API response (status + stats + chunks).
    ChunkValidationErrorSchema — Validation failure report for a single chunk.

WHY SEPARATE SCHEMAS FROM MODELS?
    Domain models (dataclasses) carry business logic and internal structure.
    Pydantic schemas serve the serialization boundary — they validate API
    inputs, enforce JSON field names, and provide OpenAPI documentation.
    Conflating the two leads to coupling between infrastructure and domain.

SOLID: Single Responsibility — only defines data contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ─── Chunk Metadata ───────────────────────────────────────────────────────────

class ChunkMetadataSchema(BaseModel):
    """
    Metadata preserved from the PDF Parser and forwarded into every chunk.

    This schema mirrors the metadata dict stored in each LangChain Document
    produced by the PDF Parser. All fields are mandatory — any missing field
    indicates a parsing defect and will be caught during validation.
    """

    document_id: str = Field(..., description="UUID of the parent document.")
    document_name: str = Field(..., description="Original PDF filename.")
    category: str = Field(..., description="Legal document category.")
    page_number: int = Field(..., ge=1, description="1-based page number.")
    file_path: str = Field(..., description="Absolute path to the source PDF.")
    source: str = Field(..., description="Source filename (same as document_name).")

    model_config = {"frozen": True}


# ─── Canonical Output Schema (chunks.json format) ─────────────────────────────

class ChunkSchema(BaseModel):
    """
    Canonical chunk record — the format written to chunks.json and returned
    by the chunking API endpoint.

    This schema is the minimum required representation for downstream
    Embedding and Elasticsearch pipelines. Extended fields are in ChunkDetailSchema.
    """

    chunk_id: str = Field(
        ...,
        description="Globally unique chunk identifier. Format: <doc_prefix>_PAGE<PPP>_CHUNK<CCC>.",
        examples=["1808ca0c_PAGE015_CHUNK003"],
    )
    document_name: str = Field(..., description="Source PDF filename.")
    page: int = Field(..., ge=1, description="1-based page number.")
    category: str = Field(..., description="Legal document category.")
    text: str = Field(..., description="Extracted chunk text content.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "chunk_id": "1808ca0c_PAGE015_CHUNK003",
                "document_name": "Title11.pdf",
                "page": 15,
                "category": "Acts",
                "text": "This is a split segment of page text from a legal document...",
            }
        }
    }


# ─── Extended Chunk Schema ────────────────────────────────────────────────────

class ChunkDetailSchema(BaseModel):
    """
    Extended chunk schema including all internal fields.

    Used for internal pipeline communication and detailed audit logs.
    The Embedding Pipeline receives this schema to build vector payloads.
    """

    chunk_id: str = Field(..., description="Globally unique chunk identifier.")
    document_id: str = Field(..., description="UUID of the parent document.")
    document_name: str = Field(..., description="Source PDF filename.")
    category: str = Field(..., description="Legal document category.")
    page_number: int = Field(..., ge=1, description="1-based page number.")
    chunk_index: int = Field(..., ge=0, description="0-based index within the page.")
    text: str = Field(..., description="Chunk text content.")
    chunk_size: int = Field(..., ge=0, description="Target size constraint (characters).")
    char_count: int = Field(..., ge=0, description="Actual character count of the text.")
    token_estimate: int = Field(..., ge=0, description="Estimated token count (chars ÷ 4).")
    file_path: str = Field(..., description="Absolute path to the source PDF.")
    source: str = Field(..., description="Source filename.")
    metadata: ChunkMetadataSchema = Field(..., description="Preserved parser metadata.")


# ─── Statistics Schemas ───────────────────────────────────────────────────────

class ChunkStatisticsSchema(BaseModel):
    """Response schema summarizing a single document's chunking execution."""

    document_id: str = Field(..., description="UUID of the chunked document.")
    document_name: str = Field(..., description="PDF filename for display.")
    total_chunks: int = Field(..., ge=0, description="Total chunks produced.")
    avg_chunk_size: float = Field(..., ge=0, description="Mean character length of chunks.")
    max_chunk_size: int = Field(..., ge=0, description="Largest chunk in characters.")
    min_chunk_size: int = Field(..., ge=0, description="Smallest chunk in characters.")
    chunks_per_page: Dict[str, int] = Field(
        ...,
        description="Chunk distribution across pages. Keys are string page numbers.",
    )
    processed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of when chunking completed.",
    )


class GlobalChunkStatsSchema(BaseModel):
    """Statistics schema for a full-dataset batch chunking run."""

    total_documents: int = Field(..., ge=0, description="Number of documents processed.")
    total_chunks: int = Field(..., ge=0, description="Total chunks across all documents.")
    avg_chunk_size: float = Field(..., ge=0, description="Grand average chunk size (chars).")
    max_chunk_size: int = Field(..., ge=0, description="Largest single chunk (chars).")
    min_chunk_size: int = Field(..., ge=0, description="Smallest single chunk (chars).")
    chunks_per_document: Dict[str, int] = Field(
        ...,
        description="Chunk counts keyed by document_id.",
    )
    failed_documents: List[str] = Field(
        default_factory=list,
        description="List of document_ids that failed during chunking.",
    )
    run_started_at: Optional[datetime] = Field(default=None)
    run_completed_at: Optional[datetime] = Field(default=None)


# ─── API Response Schemas ─────────────────────────────────────────────────────

class ChunkingResponseSchema(BaseModel):
    """Full response returned by POST /chunker/chunk/{document_id}."""

    document_id: str = Field(..., description="UUID of the processed document.")
    document_name: str = Field(..., description="PDF filename.")
    status: str = Field(..., description="Processing status (success | failed).")
    statistics: ChunkStatisticsSchema = Field(..., description="Chunking statistics.")
    chunks: List[ChunkSchema] = Field(..., description="All chunks produced.")


class ChunkValidationErrorSchema(BaseModel):
    """Schema representing a validation failure for a single chunk candidate."""

    chunk_index: int = Field(..., description="Index of the failed chunk within the page.")
    page_number: int = Field(..., description="Page number where the failure occurred.")
    error_type: str = Field(
        ...,
        description="Type of validation error: empty_chunk | duplicate_chunk | invalid_metadata | missing_page.",
    )
    detail: str = Field(..., description="Human-readable description of the failure.")
