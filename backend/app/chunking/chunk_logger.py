"""
app/chunking/chunk_logger.py
=============================
Dedicated logger for the Intelligent Chunking Module.

PURPOSE:
    Provides a pre-bound Loguru logger instance scoped to the 'dataset'
    subsystem. All chunk-related log entries — document start, page start,
    chunk creation, statistics, validation errors — are routed through this
    logger to logs/dataset/dataset.log and stdout (in development).

DESIGN:
    - Single module-level logger instance (chunk_log)
    - Bound to the 'dataset' subsystem to co-locate parsing + chunking logs
    - Loguru's .bind() mechanism routes messages to the correct file sink
    - No logger configuration here — see app.logging.logger for sink setup

WHY A DEDICATED LOGGER?
    Keeping the chunking logger separate from the root logger ensures:
        1. Log entries are clearly tagged by subsystem (dataset vs embedding)
        2. Rotating file sinks can filter by subsystem name
        3. Log verbosity can be tuned per-subsystem without affecting others

SOLID: Single Responsibility — only exposes the bound logger instance.
"""

from __future__ import annotations

from app.logging.logger import get_logger

# ─── Module-level bound logger ────────────────────────────────────────────────
# Logs all chunking activity (document start, page splits, stats, errors)
# to the 'dataset' subsystem sink → logs/dataset/dataset.log.
chunk_log = get_logger("dataset")
