"""
app/dataset/dataset_logger.py
==============================
Dedicated logger for the Dataset Management Module.

PURPOSE:
    Provides a pre-bound Loguru logger instance scoped to the 'dataset'
    subsystem. Every log record written through this logger is routed to
    logs/dataset/dataset.log via the central logging configuration in
    app/logging/logger.py.

WHY A DEDICATED LOGGER:
    - Log isolation: dataset events are searchable in isolation without
      filtering through the general app.log
    - Consistent log format across all dataset operations
    - No configuration duplication — piggybacks the central Loguru setup

USAGE:
    from app.dataset.dataset_logger import dataset_log

    dataset_log.info("Scanning folder | path={path}", path=str(folder))
    dataset_log.error("Invalid PDF | file={file}", file=file_name)

SOLID: Single Responsibility — only provides the dataset logger binding.
"""

from __future__ import annotations

from app.logging.logger import get_logger

# ─── Module-level pre-bound logger ────────────────────────────────────────────
# Import this name anywhere in the dataset module. Do not call get_logger()
# again — use this singleton to avoid creating multiple bindings.
dataset_log = get_logger("dataset")

__all__ = ["dataset_log"]
