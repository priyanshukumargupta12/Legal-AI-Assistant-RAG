"""
app/llm/llm_schemas.py
======================
Pydantic V2 schemas for LLM HTTP request and response models.

PURPOSE:
    Provides validation structures for API requests and outputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CitationSchema(BaseModel):
    """Schema for document citations."""
    model_config = ConfigDict(frozen=True)

    document: str = Field(..., description="Name of source PDF document")
    page: int = Field(..., ge=1, description="1-based page number")
    category: str = Field(..., description="Legal category classification")
    snippet: Optional[str] = Field(default=None, description="Retrieved supporting text snippet")


class LLMQueryRequest(BaseModel):
    """Request schema for querying the LLM module."""
    model_config = ConfigDict(frozen=True)

    query: str = Field(..., min_length=1, max_length=2000, description="Natural language question")
    category_filter: Optional[str] = Field(default=None, description="Optional category filter to restrict search")
    document_filter: Optional[str] = Field(default=None, description="Optional document ID to restrict search")


class LLMQueryResponse(BaseModel):
    """
    Response schema returning the answers, summaries, citations, and confidence.
    Matches the exact JSON schema requested by the user.
    """
    model_config = ConfigDict(frozen=True)

    answer: str = Field(..., description="The direct response generated from retrieved context only")
    summary: str = Field(..., description="Concise summary (max 150 words)")
    citations: List[CitationSchema] = Field(default_factory=list, description="Unique source attributions")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Generated confidence score")
