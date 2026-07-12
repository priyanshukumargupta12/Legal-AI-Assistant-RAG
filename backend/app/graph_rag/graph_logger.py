"""
app/graph_rag/graph_logger.py
==============================
Dedicated Loguru logger for the Graph RAG subsystem.

PURPOSE:
    Provides a module-scoped logger bound to the "graph" subsystem name.
    All Graph RAG components import from here to ensure consistent,
    filterable log records routed to logs/graph/graph.log.

DESIGN:
    - Thin wrapper around the centralized get_logger() factory.
    - Single import point so the subsystem name is never a magic string.

SOLID: Single Responsibility — logger binding only.
"""

from __future__ import annotations

from app.logging.logger import get_logger

# Bound logger for the entire graph_rag subsystem
graph_log = get_logger("graph")  # type: ignore[arg-type]
