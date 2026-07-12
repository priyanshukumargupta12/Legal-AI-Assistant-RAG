"""
schemas/query_schema.py
=======================
Pydantic v2 request and response schemas for the /query API endpoint.

PURPOSE:
    Define the exact shape of HTTP request bodies and response payloads
    for the query feature. FastAPI uses these for automatic validation,
    serialization, and OpenAPI documentation generation.

DESIGN:
    - Inherits from pydantic.BaseModel (v2)
    - Request schemas validate and constrain user input at the HTTP boundary
    - Response schemas define the exact JSON structure returned to the frontend
    - No business logic — purely data shape definitions

SOLID: Single Responsibility — only query API data shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    """
    Request body for POST /api/v1/query.

    Validates the user's legal question and optional filters.
    """

    question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Legal question to answer using the document corpus.",
        examples=["What are the penalties for tax evasion under the IRC?"],
    )
    category_filter: Optional[str] = Field(
        default=None,
        description="Restrict retrieval to a specific document category.",
        examples=["Acts", "Tax", "CourtJudgement", "Legal_opinion"],
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional client session ID for grouping history.",
    )

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        """Remove leading/trailing whitespace from the question."""
        return value.strip()

    @field_validator("category_filter")
    @classmethod
    def validate_category(cls, value: Optional[str]) -> Optional[str]:
        """Ensure category_filter is one of the valid categories."""
        if value is None:
            return None
        valid = {"Acts", "CourtJudgement", "Tax", "Legal_opinion"}
        if value not in valid:
            raise ValueError(f"category_filter must be one of {valid}")
        return value

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What does the Tax Cuts and Jobs Act say about corporate tax rates?",
                "category_filter": "Acts",
            }
        }
    }


class CitationSchema(BaseModel):
    """A single source citation in the query response."""

    document_name: str = Field(..., description="Source PDF filename.")
    page_number: int = Field(..., ge=1, description="Source page number (1-based).")
    category: str = Field(..., description="Document category.")
    excerpt: str = Field(..., description="Short excerpt from the source chunk.")
    rrf_score: float = Field(..., ge=0.0, description="Reciprocal Rank Fusion score.")
    rank: int = Field(..., ge=1, le=5, description="Result rank (1 = most relevant).")


class QueryResponse(BaseModel):
    """
    Response body for POST /api/v1/query.

    Contains the answer, summary, citations, and metadata.
    """

    query_id: str = Field(..., description="Unique ID for this query.")
    question: str = Field(..., description="The original sanitized question.")
    answer: str = Field(
        ...,
        description="LLM-generated answer grounded in retrieved documents.",
    )
    summary: str = Field(
        ...,
        description="2–3 sentence plain-language summary of the answer.",
    )
    citations: List[CitationSchema] = Field(
        default_factory=list,
        description="Source citations ordered by relevance.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score derived from RRF top result score.",
    )
    llm_provider: str = Field(..., description="LLM provider used (gemini | openai).")
    retrieval_count: int = Field(..., ge=0, description="Number of chunks retrieved.")
    response_time_ms: int = Field(..., ge=0, description="End-to-end latency in ms.")
    created_at: datetime = Field(..., description="UTC timestamp of the query.")

    model_config = {"from_attributes": True}
