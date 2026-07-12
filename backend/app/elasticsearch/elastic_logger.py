"""
app/elasticsearch/elastic_logger.py
====================================
Loguru-based logger for the Elasticsearch subsystem.

PURPOSE:
    Provides a single bound logger instance (`elastic_log`) used by all
    Elasticsearch module files. Routes log entries to the ``elasticsearch``
    subsystem sink so they are separated from other subsystem logs.

DESIGN:
    - Singleton pattern via module-level import
    - Loguru structured key=value logging for machine-readable output
    - Consistent with the project's existing logger pattern

SOLID: Single Responsibility — only initialises and exposes the logger.
"""

from __future__ import annotations

from loguru import logger

# ── bind the subsystem tag so every log line carries it ──────────────────────
elastic_log = logger.bind(subsystem="elasticsearch")
