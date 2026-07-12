"""
app/vectorstore/vector_logger.py
=================================
Dedicated logger for the Qdrant Vector Store module.

PURPOSE:
    Exposes a bound Loguru logger for all vector store activity.
    Logs are written to logs/retrieval/retrieval.log.
"""

from __future__ import annotations

from app.logging.logger import get_logger

# ─── Module-level bound logger ────────────────────────────────────────────────
# Logs all vector store and client actions (connect, create collection, upsert, query)
# to the 'retrieval' subsystem sink → logs/retrieval/retrieval.log.
vector_log = get_logger("retrieval")
