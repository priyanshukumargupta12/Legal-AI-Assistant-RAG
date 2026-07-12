"""
schemas/document_schema.py
==========================
Pydantic v2 request and response schemas for document ingestion endpoints.

PURPOSE:
    Define validated data shapes for:
    - Document upload responses
    - Document listing
    - Dataset scan responses

DESIGN:
    - All schemas inherit from pydantic.BaseModel (v2)
    - Matches domain entity fields but adds HTTP-specific structure
    - Used by FastAPI routers for automatic serialization

SOLID: Single Responsibility — only document API data shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response returned after a successful PDF upload and ingestion."""

    document_id: str = Field(..., description="Unique document UUID.")
    file_name: str = Field(..., description="Uploaded PDF filename.")
    category: str = Field(..., description="Document category.")
    page_count: int = Field(..., ge=1, description="Number of pages parsed.")
    chunk_count: int = Field(..., ge=1, description="Number of chunks created and indexed.")
    message: str = Field(..., description="Human-readable success message.")


class DocumentListItem(BaseModel):
    """A single document entry in the document listing response."""

    document_id: str
    file_name: str
    category: str
    file_size_bytes: int
    page_count: int
    status: str
    ingested_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Paginated list of indexed documents."""

    total: int = Field(..., description="Total number of documents in the system.")
    documents: List[DocumentListItem] = Field(
        default_factory=list,
        description="List of document metadata entries.",
    )


class DatasetScanResponse(BaseModel):
    """Response returned after scanning the dataset directory."""

    total_pdfs: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    acts_count: int
    court_count: int
    tax_count: int
    legal_opinion_count: int
    avg_pages: float
    scanned_at: datetime
    message: str


class ErrorResponse(BaseModel):
    """Standard error response returned by all exception handlers."""

    error: str = Field(..., description="Error type / exception class name.")
    message: str = Field(..., description="Human-readable error description.")
    detail: dict = Field(default_factory=dict, description="Optional error context.")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "InvalidDocumentError",
                "message": "The uploaded file is not a valid PDF.",
                "detail": {"file_name": "document.docx"},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        }
    }


class HealthResponse(BaseModel):
    """Response for the GET /health endpoint."""

    status: str = Field(..., description="Overall system health: healthy | degraded | unhealthy.")
    version: str = Field(..., description="Application version string.")
    services: dict = Field(
        default_factory=dict,
        description="Status of each dependent service.",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
