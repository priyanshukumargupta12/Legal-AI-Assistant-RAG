"""
app/api/middlewares/rate_limit_middleware.py
============================================
Lightweight sliding-window rate limiting middleware.

PURPOSE:
    Enforces maximum request limits per IP address to protect API endpoints
    from abuse and denial-of-service (DoS) attempts.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings
from app.logging.logger import get_logger

log = get_logger("security")
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter middleware.
    Tracks client requests by IP and enforces limit configured in Settings.
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()
        self._limit = settings.rate_limit_per_minute
        self._window = 60.0  # 1 minute sliding window

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass rate limit checks for documentation or health checks
        path = request.url.path
        if path in ("/docs", "/redoc", "/openapi.json", "/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        with self._lock:
            # Clean up old timestamps
            self._requests[client_ip] = [
                t for t in self._requests[client_ip]
                if now - t < self._window
            ]

            # Enforce limit
            if len(self._requests[client_ip]) >= self._limit:
                log.warning(
                    "Rate limit exceeded | ip={ip} | count={count} | limit={limit}",
                    ip=client_ip,
                    count=len(self._requests[client_ip]),
                    limit=self._limit,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "TooManyRequests",
                        "message": "Too many requests. Please try again in a minute.",
                        "detail": {"ip": client_ip, "limit": self._limit},
                    },
                )

            # Record current request
            self._requests[client_ip].append(now)

        return await call_next(request)
