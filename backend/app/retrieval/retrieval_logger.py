"""
app/retrieval/retrieval_logger.py
====================================
Loguru-based logger for the Hybrid Retrieval subsystem.

PURPOSE:
    Provides a single bound logger instance (``retrieval_log``) used by all
    retrieval module files. Routes log entries to the ``retrieval`` subsystem
    sink so they are separated from embedding and Elasticsearch logs.

SOLID: Single Responsibility — only initialises and exposes the logger.
"""

from __future__ import annotations

from loguru import logger

# ── bind the subsystem tag so every log line carries it ──────────────────────
retrieval_log = logger.bind(subsystem="retrieval")
