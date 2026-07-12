"""
middlewares/cors_middleware.py
===============================
CORS middleware configuration.

PURPOSE:
    Configures Cross-Origin Resource Sharing (CORS) for the FastAPI app.
    Allows the React frontend origin to make API requests.

DESIGN:
    Applied in main.py using app.add_middleware(CORSMiddleware, ...).
    Origins loaded from settings.cors_origins.

SOLID: Single Responsibility — CORS configuration only.
"""

from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware

# TODO: Wire into main.py in Milestone 10 (FastAPI Presentation Layer)
