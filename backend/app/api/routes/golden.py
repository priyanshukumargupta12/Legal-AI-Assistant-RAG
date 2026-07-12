"""
app/api/routes/golden.py
=========================
API route proxy for the Golden Set Management Module.

PURPOSE:
    Imports the golden set router from golden_controller and re-exports it
    for inclusion in the v1 API router (app/api/v1/router.py).

SOLID: Single Responsibility — route registration proxy only.
"""

from __future__ import annotations

from app.golden_set.golden_controller import router

__all__ = ["router"]
