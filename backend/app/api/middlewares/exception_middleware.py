"""
app/api/middlewares/exception_middleware.py
============================================
Global exception handling middleware.

PURPOSE:
    Intercepts unhandled exceptions globally and maps them to unified StandardResponse envelopes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.exceptions import LegalAssistantError
from app.api.exceptions.api_exceptions import APIException
from app.logging.logger import get_logger

logger = get_logger("api")



from fastapi import HTTPException

class ExceptionTranslationMiddleware(BaseHTTPMiddleware):
    """
    Middleware catching all domain and system exceptions, translating them
    into compliant JSON envelopes.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except APIException as exc:
            logger.warning("API Presentation Exception: {msg}", msg=exc.message)
            return self._build_error_response(exc.status_code, exc.message, exc.detail)

        except HTTPException as exc:
            logger.warning("HTTP Exception: {detail}", detail=exc.detail)
            return self._build_error_response(exc.status_code, str(exc.detail))

        except LegalAssistantError as exc:
            # Map domain exceptions to relevant HTTP status codes
            logger.error("Domain exception: {err} | {msg}", err=type(exc).__name__, msg=exc.message)
            status_code = getattr(exc, "status_code", 500)
            return self._build_error_response(status_code, exc.message, exc.detail)

        except ValueError as exc:
            # Catch query validations
            logger.warning("Validation ValueError: {msg}", msg=str(exc))
            return self._build_error_response(422, str(exc))

        except Exception as exc:
            # Catch-all safety net
            logger.exception("Global exception caught: {msg}", msg=str(exc))
            return self._build_error_response(
                500,
                "An unexpected internal error occurred. Please try again later."
            )

    @staticmethod
    def _build_error_response(status_code: int, message: str, detail: dict | None = None) -> Response:
        """Constructs a standard error JSON response."""
        payload = {
            "status": "error",
            "message": message,
            "data": detail or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return Response(
            content=json.dumps(payload),
            media_type="application/json",
            status_code=status_code
        )
