"""
middlewares/logging_middleware.py
==================================
HTTP request/response logging middleware.

PURPOSE:
    Logs every incoming request and outgoing response with:
    - HTTP method, path, query params
    - Response status code
    - Request processing time in milliseconds

DESIGN:
    Implemented as a Starlette BaseHTTPMiddleware subclass.
    Uses the 'api' logger.

SOLID: Single Responsibility — HTTP logging only.
"""

from __future__ import annotations

# TODO: Implement in Milestone 10 (FastAPI Presentation Layer)
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every HTTP request and response.

    Methods to implement:
        dispatch(request, call_next) -> Response
    """
    pass
