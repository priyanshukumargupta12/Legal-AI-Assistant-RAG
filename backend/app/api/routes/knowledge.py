"""
app/api/routes/knowledge.py
==============================
FastAPI proxy route for the OKF Knowledge module.

PURPOSE:
    Thin proxy that re-exports the knowledge_controller router for registration
    in api/v1/router.py. Follows the same pattern as all other route files.

SOLID: Single Responsibility — route registration only.
"""

from __future__ import annotations

from app.knowledge.knowledge_controller import router

__all__ = ["router"]
