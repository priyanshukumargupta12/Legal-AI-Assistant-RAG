"""
app/pdf_parser/parser_logger.py
================================
Dedicated logger for the PDF Parsing Module.

PURPOSE:
    Provides a pre-bound Loguru logger instance scoped to the 'pdf_parser'
    subsystem. Logs are routed to logs/app/app.log and logs/dataset/dataset.log
    (or standard outputs) depending on severity.

SOLID: Single Responsibility — only provides the logger binding.
"""

from __future__ import annotations

from app.logging.logger import get_logger

# ─── Module-level bound logger ────────────────────────────────────────────────
# Routes logging messages with correct subsystem tagging.
parser_log = get_logger("dataset")  # Logs parsed document metadata to dataset
