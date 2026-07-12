"""
app/golden_set/__init__.py
===========================
Golden Set Management Module package initializer.

PURPOSE:
    The Golden Set Management Module manages the import, validation,
    statistical analysis, and export of golden question-answer pairs
    used to benchmark the Hybrid RAG pipeline accuracy.

    The module is architecturally extensible to support future use cases:
        - RAG Benchmarking (current)
        - Retrieval Optimization (future)
        - Prompt Optimization (future)
        - LLM Fine-Tuning (future)

    See golden_extensions.py for the abstract interfaces that enable extension.

EXPORTS:
    GoldenSetService      — primary orchestration service
    GoldenRecord          — core domain model
    GoldenSetStatistics   — aggregate statistics model
    GoldenSetExportConfig — use-case export configuration
    GoldenSetUseCase      — enum: rag_benchmarking | retrieval_optimization | ...
    ExportFormat          — enum: csv | xlsx | json | jsonl | parquet
    DataSplit             — enum: train | validation | test | unassigned
    GoldenSetRegistry     — singleton adapter/exporter registry (see golden_extensions)

USAGE:
    from app.golden_set import GoldenSetService
    from app.golden_set import GoldenSetUseCase, ExportFormat, GoldenSetExportConfig
    from app.golden_set.golden_extensions import GoldenSetAdapter, GoldenSetRegistry
"""

from __future__ import annotations

from app.golden_set.golden_models import (
    DataSplit,
    ExportFormat,
    GoldenRecord,
    GoldenSetExportConfig,
    GoldenSetStatistics,
    GoldenSetUseCase,
)
from app.golden_set.golden_service import GoldenSetService

__all__ = [
    "GoldenSetService",
    "GoldenRecord",
    "GoldenSetStatistics",
    "GoldenSetExportConfig",
    "GoldenSetUseCase",
    "ExportFormat",
    "DataSplit",
]
