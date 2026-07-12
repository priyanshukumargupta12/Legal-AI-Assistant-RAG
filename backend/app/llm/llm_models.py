"""
app/llm/llm_models.py
======================
Domain models for the LLM Module.

PURPOSE:
    Defines pure Python dataclasses used to hold generated answers, citations,
    confidence metrics, and chat history. Free from database and framework code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Citation:
    """
    Represents a specific source document attribution.

    Attributes:
        document: The name of the source PDF.
        page:     The 1-based page number.
        category: The category classification of the source document.
    """
    document: str
    page: int
    category: str
    snippet: Optional[str] = None


@dataclass(frozen=True)
class LLMResult:
    """
    Encapsulates the complete structured response from the LLM.

    Attributes:
        answer:           The direct response to the user query.
        summary:          A summary of the answer (max 150 words).
        citations:        List of unique documents supporting the answer.
        confidence_score: Generated confidence score (0.0 to 1.0).
    """
    answer: str
    summary: str
    citations: List[Citation] = field(default_factory=list)
    confidence_score: float = 0.0


@dataclass(frozen=True)
class ChatMessage:
    """
    Represents an entry in the conversation history memory.

    Attributes:
        question:  User input query.
        answer:    LLM generated response text.
        timestamp: When the exchange occurred (UTC).
    """
    question: str
    answer: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
