"""
core/exceptions.py
==================
Custom exception hierarchy for the Enterprise AI Legal Assistant.

PURPOSE:
    Define domain-specific exceptions for every subsystem.
    Raised by services and repositories; caught and translated to HTTP
    responses by FastAPI exception handlers in main.py.

DESIGN:
    - All exceptions extend LegalAssistantError (base)
    - Each subsystem has its own exception class
    - Exceptions carry a human-readable message and optional detail dict
    - Never expose internal stack traces through HTTP responses

SOLID: Each exception class represents exactly one error category.
"""

from __future__ import annotations

from typing import Any, Optional


class LegalAssistantError(Exception):
    """
    Base exception for all domain-specific errors in this application.

    All custom exceptions inherit from this class, enabling a single
    catch-all handler while still allowing specific subsystem handling.

    Attributes:
        message: Human-readable error description.
        detail:  Optional dict with additional context for debugging.
        status_code: Suggested HTTP status code for API responses.
    """

    def __init__(
        self,
        message: str,
        detail: Optional[dict[str, Any]] = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, status_code={self.status_code})"


# ─── Dataset & PDF Exceptions ─────────────────────────────────────────────────

class DatasetScanError(LegalAssistantError):
    """Raised when the dataset directory cannot be scanned."""

    def __init__(self, message: str, detail: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message=message, detail=detail, status_code=500)


class PDFParseError(LegalAssistantError):
    """Raised when a PDF file cannot be parsed by PyMuPDF."""

    def __init__(self, message: str, file_path: Optional[str] = None) -> None:
        detail = {"file_path": file_path} if file_path else {}
        super().__init__(message=message, detail=detail, status_code=422)


class InvalidDocumentError(LegalAssistantError):
    """Raised when an uploaded file is not a valid PDF."""

    def __init__(self, message: str, file_name: Optional[str] = None) -> None:
        detail = {"file_name": file_name} if file_name else {}
        super().__init__(message=message, detail=detail, status_code=400)


class DuplicateDocumentError(LegalAssistantError):
    """Raised when an uploaded document is a duplicate of an existing one."""

    def __init__(self, file_name: str, existing_hash: str) -> None:
        super().__init__(
            message=f"Document '{file_name}' already exists in the system.",
            detail={"file_name": file_name, "md5_hash": existing_hash},
            status_code=409,
        )


# ─── Chunking Exceptions ──────────────────────────────────────────────────────

class ChunkingError(LegalAssistantError):
    """Raised when text splitting or chunk building fails."""

    def __init__(self, message: str, document_id: Optional[str] = None) -> None:
        detail = {"document_id": document_id} if document_id else {}
        super().__init__(message=message, detail=detail, status_code=500)


# ─── Embedding Exceptions ─────────────────────────────────────────────────────

class EmbeddingError(LegalAssistantError):
    """Raised when the embedding model fails to encode a batch of texts."""

    def __init__(self, message: str, batch_size: Optional[int] = None) -> None:
        detail = {"batch_size": batch_size} if batch_size else {}
        super().__init__(message=message, detail=detail, status_code=500)


class EmbeddingModelLoadError(LegalAssistantError):
    """Raised when the sentence-transformers model cannot be loaded."""

    def __init__(self, model_name: str, reason: str) -> None:
        super().__init__(
            message=f"Failed to load embedding model '{model_name}': {reason}",
            detail={"model_name": model_name, "reason": reason},
            status_code=503,
        )


# ─── Vector Store Exceptions ──────────────────────────────────────────────────

class VectorStoreError(LegalAssistantError):
    """Raised when a Qdrant operation fails (upsert, search, connection)."""

    def __init__(self, message: str, operation: Optional[str] = None) -> None:
        detail = {"operation": operation} if operation else {}
        super().__init__(message=message, detail=detail, status_code=503)


class VectorStoreConnectionError(VectorStoreError):
    """Raised when the application cannot connect to Qdrant."""

    def __init__(self, url: str) -> None:
        super().__init__(
            message=f"Cannot connect to Qdrant at {url}.",
            operation="connect",
        )


# ─── Elasticsearch Exceptions ─────────────────────────────────────────────────

class KeywordStoreError(LegalAssistantError):
    """Raised when an Elasticsearch operation fails."""

    def __init__(self, message: str, operation: Optional[str] = None) -> None:
        detail = {"operation": operation} if operation else {}
        super().__init__(message=message, detail=detail, status_code=503)


class KeywordStoreConnectionError(KeywordStoreError):
    """Raised when the application cannot connect to Elasticsearch."""

    def __init__(self, url: str) -> None:
        super().__init__(
            message=f"Cannot connect to Elasticsearch at {url}.",
            operation="connect",
        )


# ─── Retrieval Exceptions ─────────────────────────────────────────────────────

class RetrievalError(LegalAssistantError):
    """Raised when the hybrid retriever fails to complete a search."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=500)


# ─── LLM Exceptions ───────────────────────────────────────────────────────────

class LLMError(LegalAssistantError):
    """Raised when the LLM API call fails or returns an invalid response."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        detail = {"provider": provider} if provider else {}
        super().__init__(message=message, detail=detail, status_code=503)


class LLMResponseParseError(LegalAssistantError):
    """Raised when the LLM response cannot be parsed into the expected schema."""

    def __init__(self, raw_response: str) -> None:
        super().__init__(
            message="Failed to parse LLM response into structured format.",
            detail={"raw_response": raw_response[:500]},
            status_code=500,
        )


class PromptInjectionError(LegalAssistantError):
    """Raised when user input is detected as a prompt injection attempt."""

    def __init__(self) -> None:
        super().__init__(
            message="Input contains disallowed patterns and cannot be processed.",
            status_code=400,
        )


# ─── Ingestion Exceptions ─────────────────────────────────────────────────────

class IngestionError(LegalAssistantError):
    """Raised when the full document ingestion pipeline fails."""

    def __init__(self, message: str, document_name: Optional[str] = None) -> None:
        detail = {"document_name": document_name} if document_name else {}
        super().__init__(message=message, detail=detail, status_code=500)


# ─── Evaluation Exceptions ────────────────────────────────────────────────────

class EvaluationError(LegalAssistantError):
    """Raised when the golden set evaluation pipeline fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=500)


class GoldenSetImportError(LegalAssistantError):
    """Raised when the golden set file is invalid or missing required columns."""

    def __init__(self, message: str, missing_columns: Optional[list[str]] = None) -> None:
        detail = {"missing_columns": missing_columns} if missing_columns else {}
        super().__init__(message=message, detail=detail, status_code=422)


# ─── Generic Not Found ────────────────────────────────────────────────────────

class ResourceNotFoundError(LegalAssistantError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource_type} '{identifier}' not found.",
            detail={"resource_type": resource_type, "identifier": identifier},
            status_code=404,
        )
