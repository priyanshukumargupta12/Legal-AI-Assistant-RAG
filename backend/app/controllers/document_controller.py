"""
controllers/document_controller.py
====================================
HTTP controller for document management endpoints.

PURPOSE:
    Thin layer between FastAPI router and DocumentIngestionService.
    Translates HTTP request objects into service calls and
    service responses into HTTP responses.

    Controllers do NOT contain business logic — they delegate immediately
    to the appropriate service.

ENDPOINTS HANDLED:
    POST /api/v1/documents/ingest   → Upload and ingest a single PDF
    POST /api/v1/documents/ingest-all → Trigger bulk ingestion of dataset/
    GET  /api/v1/documents          → List all indexed documents

SOLID: Single Responsibility — HTTP translation only.
"""

from __future__ import annotations

# TODO: Implement in Milestone 9 (Application Services + API Layer)
# Dependencies to inject via FastAPI Depends():
#   - DocumentIngestionService
#   - DatasetService


class DocumentController:
    """
    Controller for document upload and listing operations.

    Injected by FastAPI's dependency injection via Depends().
    Delegates all logic to DocumentIngestionService.
    """

    pass
