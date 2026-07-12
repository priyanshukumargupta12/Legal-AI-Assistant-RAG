"""
app/evaluation
==============
RAG Pipeline Evaluation Module.

EXPORTS:
    EvaluationService - primary service orchestrator
    MetricsCalculator - stateless metrics calculator
    GoldenSetImporter - csv/xlsx golden set loader
"""

from __future__ import annotations

from app.evaluation.evaluation_service import EvaluationService
from app.evaluation.metrics import MetricsCalculator
from app.evaluation.golden_set import GoldenSetImporter

__all__ = [
    "EvaluationService",
    "MetricsCalculator",
    "GoldenSetImporter",
]
