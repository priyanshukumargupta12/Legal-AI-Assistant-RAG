"""
app/llm/llm_logger.py
======================
Loguru-based logger for the LLM subsystem.

PURPOSE:
    Bound loguru logger configured with 'llm' subsystem tag for isolated log filters.
"""

from __future__ import annotations
from loguru import logger

llm_log = logger.bind(subsystem="llm")
