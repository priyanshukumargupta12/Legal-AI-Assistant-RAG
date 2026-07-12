"""
middlewares/rate_limit_middleware.py
=====================================
Rate limiting configuration using slowapi.

PURPOSE:
    Applies per-IP rate limits to query endpoints using slowapi.
    Prevents abuse and protects LLM API quota.

LIMIT: 60 requests/minute per IP (configurable via RATE_LIMIT_PER_MINUTE)

SOLID: Single Responsibility — rate limiting only.
"""

from __future__ import annotations

# TODO: Implement in Milestone 15 (Security + Hardening)
# from slowapi import Limiter
# from slowapi.util import get_remote_address
