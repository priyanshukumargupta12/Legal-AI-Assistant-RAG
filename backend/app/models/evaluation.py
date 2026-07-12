"""
models/evaluation.py
====================
Domain entity dataclasses for evaluation pipeline entities.

PURPOSE:
    Represents golden set entries, per-question evaluation results,
    and aggregate evaluation run reports.

DESIGN:
    - Pure Python dataclasses; no external dependencies
    - EvaluationResult holds all 6 metric scores for one Q&A pair
    - EvaluationReport aggregates across all questions

SOLID: Single Responsibility — only evaluation domain entities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class GoldenSetEntry:
    """
    A single ground-truth question-answer pair from the golden set file.

    Imported from golden_set.csv or golden_set.xlsx by GoldenSetImporter.

    Attributes:
        question:          Legal question to ask the system.
        expected_answer:   Ground truth answer text.
        relevant_doc:      Expected source document filename.
        relevant_page:     Expected source page number.
        category:          Optional category filter hint.
        difficulty:        Optional: easy | medium | hard.
    """

    question: str
    expected_answer: str
    relevant_doc: str
    relevant_page: int
    category: Optional[str] = None
    difficulty: Optional[str] = None


@dataclass
class EvaluationResult:
    """
    Evaluation metrics for a single golden set question.

    Produced by EvaluationService after running the full RAG pipeline
    on one GoldenSetEntry and computing all metric scores.

    Attributes:
        question:           The evaluated question.
        expected_answer:    Ground truth answer.
        generated_answer:   Answer produced by the RAG system.
        expected_doc:       Expected source document.
        expected_page:      Expected source page.
        retrieved_correctly: True if expected_doc/page appeared in top-5.
        precision_at_k:     Fraction of retrieved chunks that are relevant.
        recall_at_k:        Fraction of relevant chunks that were retrieved.
        faithfulness:       Score 0–1: answer grounded in retrieved context.
        context_precision:  Score 0–1: relevance of retrieved context.
        context_recall:     Score 0–1: coverage of expected answer by context.
        answer_relevancy:   Score 0–1: semantic similarity of generated vs expected.
        response_time_ms:   End-to-end latency for this question.
    """

    question: str
    expected_answer: str
    generated_answer: str
    expected_doc: str
    expected_page: int
    retrieved_correctly: bool
    precision_at_k: float
    recall_at_k: float
    faithfulness: float
    context_precision: float
    context_recall: float
    answer_relevancy: float
    response_time_ms: int


@dataclass
class EvaluationReport:
    """
    Aggregate evaluation report across all golden set questions.

    Produced by EvaluationService after processing all GoldenSetEntry items.
    Exported to evaluation_results.csv and evaluation_results.xlsx.

    Attributes:
        run_id:                   Unique UUID for this evaluation run.
        golden_set_file:          Source file name.
        total_questions:          Number of questions evaluated.
        llm_provider:             LLM provider used during evaluation.
        avg_precision_at_k:       Mean Precision@K across all questions.
        avg_recall_at_k:          Mean Recall@K across all questions.
        avg_faithfulness:         Mean Faithfulness score.
        avg_context_precision:    Mean Context Precision score.
        avg_context_recall:       Mean Context Recall score.
        avg_answer_relevancy:     Mean Answer Relevancy score.
        correct_retrieval_rate:   Fraction of questions with correct retrieval.
        results:                  Per-question result list.
        run_at:                   Timestamp of the evaluation run.
    """

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
    results: list[EvaluationResult]
    run_at: datetime = field(default_factory=datetime.utcnow)
