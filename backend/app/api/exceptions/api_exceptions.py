"""
app/api/exceptions/api_exceptions.py
=====================================
Defines custom API exceptions and translation logic.

PURPOSE:
    Provides HTTP-specific exceptions that can be thrown within routes to yield
    standardized error envelopes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import HTTPException


class APIException(HTTPException):
    """Base exception for all API presentation-layer errors."""

    def __init__(
        self,
        status_code: int,
        message: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail or {})
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
