"""
schemas/evaluation_schema.py
=============================
Pydantic v2 schemas for the evaluation API endpoints.

PURPOSE:
    Define request/response shapes for golden set import,
    evaluation run results, and metrics reporting.

SOLID: Single Responsibility — only evaluation API data shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class EvaluationResultItem(BaseModel):
    """Per-question evaluation metrics in the API response."""

    question: str
    expected_answer: str
    generated_answer: str
    expected_doc: str
    expected_page: int
    retrieved_correctly: bool
    precision_at_k: float = Field(..., ge=0.0, le=1.0)
    recall_at_k: float = Field(..., ge=0.0, le=1.0)
    faithfulness: float = Field(..., ge=0.0, le=1.0)
    context_precision: float = Field(..., ge=0.0, le=1.0)
    context_recall: float = Field(..., ge=0.0, le=1.0)
    answer_relevancy: float = Field(..., ge=0.0, le=1.0)
    response_time_ms: int

    model_config = {"from_attributes": True}


class EvaluationReportResponse(BaseModel):
    """Full evaluation report returned by GET /api/v1/evaluation/run."""

    run_id: str
    golden_set_file: str
    total_questions: int
    llm_provider: str
    avg_precision_at_k: float
    avg_recall_at_k: float
    avg_faithfulness: float
    avg_context_precision: float
    avg_context_recall: float
    avg_answer_relevancy: float
    correct_retrieval_rate: float
    results: List[EvaluationResultItem]
    run_at: datetime

    model_config = {"from_attributes": True}


class GoldenSetImportResponse(BaseModel):
    """Response after successfully importing a golden set file."""

    file_name: str
    total_entries: int
    valid_entries: int
    invalid_entries: int
    message: str
