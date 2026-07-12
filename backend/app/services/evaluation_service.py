"""
services/evaluation_service.py
================================
Service layer for golden set evaluation pipeline.

PURPOSE:
    Imports golden set, runs the full RAG pipeline on each question,
    computes all 6 evaluation metrics, and exports results.

DEPENDENCIES (injected):
    - GoldenSetImporter (infrastructure)
    - QueryService (reuse query pipeline)
    - MetricsCalculator (infrastructure)

SOLID: Single Responsibility — evaluation orchestration only.
"""

from __future__ import annotations

# TODO: Implement in Milestone 14 (Golden Set Evaluation)


class EvaluationService:
    """
    Orchestrates the golden set evaluation pipeline.

    Methods to implement:
        import_golden_set(file_path: Path) -> GoldenSetImportResponse
        run_evaluation() -> EvaluationReport
        export_results(report: EvaluationReport) -> Path
    """
    pass
