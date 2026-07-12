"""
app/embeddings/embedding_logger.py
===================================
Dedicated logger for the Embedding Module.

PURPOSE:
    Provides a pre-bound Loguru logger instance scoped to the 'embedding'
    subsystem. All embedding-related log entries — model loading, progress,
    validation failures, processing time, database insertion — are routed
    through this logger to logs/embedding/embedding.log and stdout.

SOLID: Single Responsibility — only exposes the bound logger instance.
"""

from __future__ import annotations

from app.logging.logger import get_logger

# ─── Module-level bound logger ────────────────────────────────────────────────
# Logs all embedding pipeline activities (model loading, encoding, stats, errors)
# to the 'embedding' subsystem sink → logs/embedding/embedding.log.
embedding_log = get_logger("embedding")
