"""
app/api/routes/graph_rag.py
==============================
FastAPI proxy route for the Graph RAG module.

PURPOSE:
    Thin proxy that re-exports the graph_controller router under the
    /api/v1 prefix. Follows the same pattern as all other active route files
    in this directory (parser.py, retrieval.py, etc.).

SOLID: Single Responsibility — route registration only.
"""

from __future__ import annotations

from app.graph_rag.graph_controller import router

# Re-export the controller router — registered by api/v1/router.py
__all__ = ["router"]
