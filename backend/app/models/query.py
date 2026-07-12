"""
models/query.py
===============
Domain entity dataclasses for query requests, results, and search history.

PURPOSE:
    Represents the query lifecycle — from user input through retrieval,
    LLM generation, and final structured response. Also defines the
    search history entry for persistence.

DESIGN:
    - Pure Python dataclasses; no Pydantic or FastAPI imports
    - Frozen where appropriate for immutability guarantees
    - QueryResult is the final enriched response object

SOLID: Single Responsibility — only query-domain data shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.models.document import Citation


@dataclass(frozen=True)
class Query:
    """
    Represents a validated user query entering the RAG pipeline.

    Produced by QueryService after sanitizing the raw user input.

    Attributes:
        question:         Sanitized query text from the user.
        category_filter:  Optional category to restrict retrieval scope.
        session_id:       Optional client session ID for grouping history.
    """

    question: str
    category_filter: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class QueryResult:
    """
    Complete structured result returned by the RAG pipeline to the API layer.

    Produced by QueryService after retrieval + LLM generation.

    Attributes:
        query_id:         Unique UUID for this query (used in history).
        question:         Original sanitized user question.
        answer:           LLM-generated answer (only from retrieved context).
        summary:          2–3 sentence plain-language summary of the answer.
        citations:        Ordered list of source citations (max 5).
        confidence_score: 0.0–1.0 confidence derived from RRF top score.
        llm_provider:     Which LLM generated the answer (gemini | openai).
        retrieval_count:  Number of chunks retrieved before LLM generation.
        response_time_ms: End-to-end latency in milliseconds.
        created_at:       UTC timestamp of the query.
    """

    query_id: str
    question: str
    answer: str
    summary: str
    citations: list[Citation]
    confidence_score: float
    llm_provider: str
    retrieval_count: int
    response_time_ms: int
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SearchHistoryEntry:
    """
    A single entry in the persistent search history log.

    Written by QueryService to search_history.json after every query.

    Attributes:
        search_id:        Unique UUID for this search entry.
        question:         User question text.
        category_filter:  Optional category filter used.
        answer_preview:   First 200 characters of the answer.
        retrieval_count:  Number of chunks retrieved.
        confidence_score: Final confidence score.
        llm_provider:     LLM provider used.
        response_time_ms: End-to-end latency.
        searched_at:      Timestamp of the query.
    """

    search_id: str
    question: str
    category_filter: Optional[str]
    answer_preview: str
    retrieval_count: int
    confidence_score: float
    llm_provider: str
    response_time_ms: int
    searched_at: datetime = field(default_factory=datetime.utcnow)
