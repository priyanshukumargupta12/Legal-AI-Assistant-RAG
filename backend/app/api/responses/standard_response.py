"""
app/api/responses/standard_response.py
======================================
Defines the standard envelope schema for all API responses.

PURPOSE:
    Ensures every HTTP response returned by the backend conforms to the requested layout:
        {
            "status": "success" | "error",
            "message": "User-friendly status message",
            "data": { ... },
            "timestamp": "ISO-8601 UTC timestamp"
        }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """
    Standard envelope returned by all endpoints.
    """
    status: str = Field(default="success", description="Status code ('success' or 'error')")
    message: str = Field(..., description="Human-readable informational message")
    data: T = Field(..., description="Response payload")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp"
    )

    @classmethod
    def success(cls, data: T, message: str = "Operation completed successfully.") -> StandardResponse[T]:
        """Helper to construct a success envelope."""
        return cls(status="success", message=message, data=data)

    @classmethod
    def error(cls, message: str, data: Any = None) -> StandardResponse[Any]:
        """Helper to construct an error envelope."""
        return cls(status="error", message=message, data=data or {})
