"""
app/knowledge/knowledge_logger.py
===================================
Dedicated Loguru logger for the OKF Knowledge subsystem.

PURPOSE:
    Provides a module-scoped logger bound to the "knowledge" subsystem name.
    All Knowledge module components import from here to ensure consistent,
    filterable log records routed to logs/knowledge/knowledge.log.

DESIGN:
    - Thin wrapper around the centralized get_logger() factory.
    - Single import point so the subsystem name is never a magic string.

SOLID: Single Responsibility — logger binding only.
"""

from __future__ import annotations

from app.logging.logger import get_logger

# Bound logger for the entire knowledge subsystem
knowledge_log = get_logger("knowledge")  # type: ignore[arg-type]
