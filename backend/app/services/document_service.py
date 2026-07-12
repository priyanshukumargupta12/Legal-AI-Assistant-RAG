"""
services/document_service.py
==============================
Service layer for document ingestion use case.

PURPOSE:
    Orchestrates the complete document ingestion pipeline:
    PDF parsing → chunking → embedding → Qdrant upsert → ES indexing.

    This is the primary use-case class for the document feature.
    All coordination logic lives here; infrastructure calls go through
    injected repository and infrastructure interfaces.

DEPENDENCIES (injected via constructor):
    - PDFParser (infrastructure)
    - ChunkBuilder (infrastructure)
    - BGEEmbedder (infrastructure)
    - QdrantRepository (repository)
    - ElasticsearchRepository (repository)

SOLID: Single Responsibility — document ingestion orchestration only.
       Open/Closed — new ingestion steps added without modifying existing.
       Dependency Inversion — depends on abstractions, not concrete classes.
"""

from __future__ import annotations

# TODO: Implement in Milestone 9 (Application Services)


class DocumentIngestionService:
    """
    Orchestrates the full document ingestion pipeline.

    Methods to implement:
        ingest_uploaded_file(file_path, category, file_name) -> DocumentUploadResponse
        ingest_all_from_dataset() -> List[DocumentUploadResponse]
        list_documents() -> DocumentListResponse
        get_document_by_id(document_id) -> DocumentListItem
    """
    pass
