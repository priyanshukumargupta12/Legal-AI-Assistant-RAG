"""
app/golden_set/golden_logger.py
================================
Dedicated logger for the Golden Set Management Module.

PURPOSE:
    Provides a pre-bound Loguru logger instance scoped to the 'evaluation'
    subsystem. Every log record written through this logger is routed to
    logs/evaluation/evaluation.log via the central logging configuration
    in app/logging/logger.py.

WHY A DEDICATED LOGGER:
    - Log isolation: golden set events are searchable in isolation without
      filtering through the general app.log
    - Consistent log format across all golden set operations (import,
      validation, statistics, export)
    - No configuration duplication — piggybacks the central Loguru setup

USAGE:
    from app.golden_set.golden_logger import golden_log

    golden_log.info("Import started | file={file}", file="golden_set.csv")
    golden_log.error("Validation failed | row={row}", row=42)

SOLID: Single Responsibility — only provides the golden set logger binding.
"""

from __future__ import annotations

from app.logging.logger import get_logger

# ─── Module-level pre-bound logger ────────────────────────────────────────────
# Import this name anywhere in the golden_set module. Do not call get_logger()
# again — use this singleton to avoid creating multiple bindings.
golden_log = get_logger("evaluation")

__all__ = ["golden_log"]
