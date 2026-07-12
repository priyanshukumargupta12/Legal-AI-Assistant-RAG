"""
app/api/middlewares/logging_middleware.py
=========================================
Request and response auditing middleware.

PURPOSE:
    Audits incoming routes, logs elapsed processing times, and records queries
    for security and performance tracing.
"""

from __future__ import annotations

import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.logging.logger import get_logger

logger = get_logger("api")



class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that intercepts all API calls to log method, path,
    execution latency, and return status codes.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Prevent logging path matches for health checks to keep logs clean
        path = request.url.path
        if path == "/health" or path.endswith("/health"):
            return await call_next(request)

        method = request.method
        client_host = request.client.host if request.client else "unknown"

        # Auditing start
        logger.info(
            "API Request Received | method={method} | path={path} | client={client}",
            method=method,
            path=path,
            client=client_host,
        )

        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Auditing completion
        logger.info(
            "API Response Dispatched | method={method} | path={path} | status={status} | latency={latency:.2f}ms",
            method=method,
            path=path,
            status=response.status_code,
            latency=elapsed_ms,
        )

        # Inject latency header into HTTP response for client diagnostics
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response
