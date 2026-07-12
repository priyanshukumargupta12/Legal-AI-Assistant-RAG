"""
app/knowledge/knowledge_controller.py
=======================================
FastAPI router (HTTP controller) for OKF Knowledge endpoints.

PURPOSE:
    Thin HTTP adapter between FastAPI and KnowledgeService.
    Translates HTTP requests into service calls and service outputs into
    standardized StandardResponse envelopes. Contains zero business logic.

ENDPOINTS:
    POST /knowledge/build                 — Build OKF from all indexed chunks
    GET  /knowledge/stats                 — Knowledge base statistics
    GET  /knowledge/documents             — List all KnowledgeDocument objects
    GET  /knowledge/document/{doc_id}     — Get single KnowledgeDocument by document_id
    GET  /knowledge/chunks                — List KnowledgeChunk objects (paginated)
    GET  /knowledge/chunk/{knowledge_id}  — Get single KnowledgeChunk by knowledge_id

DESIGN:
    - All dependency injection via FastAPI Depends().
    - Uniform StandardResponse envelope for all endpoints.
    - Errors translated to structured HTTP 400/404/500 responses.
    - Pagination on /chunks to prevent response size explosion.

SOLID: Single Responsibility — HTTP translation only.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.responses.standard_response import StandardResponse
from app.knowledge.knowledge_logger import knowledge_log
from app.knowledge.knowledge_models import KnowledgeChunk, KnowledgeDocument

router = APIRouter(prefix="/knowledge", tags=["OKF Knowledge"])


# =============================================================================
# DEPENDENCY TYPE ALIAS
# =============================================================================

from app.api.dependencies.services import get_knowledge_service  # noqa: E402
from app.knowledge.knowledge_service import KnowledgeService  # noqa: E402
KnowledgeServiceDep = Annotated[KnowledgeService, Depends(get_knowledge_service)]


# =============================================================================
# SERIALIZATION HELPERS
# =============================================================================

def _doc_to_summary(doc: KnowledgeDocument) -> dict:
    """Serialize a KnowledgeDocument to a compact summary dict (no full entity list)."""
    return {
        "document_id": doc.document_id,
        "knowledge_id": doc.knowledge_id,
        "document_name": doc.document_name,
        "category": doc.category,
        "source": doc.source,
        "total_pages": doc.total_pages,
        "total_chunks": doc.total_chunks,
        "top_keywords": doc.top_keywords,
        "entity_count": len(doc.all_entities),
        "reference_count": len(doc.all_references),
        "legal_section_count": len(doc.all_legal_sections),
        "relation_count": len(doc.all_relationships),
        "knowledge_chunk_ids": doc.knowledge_chunk_ids,
        "created_at": doc.created_at.isoformat(),
    }


def _chunk_to_summary(chunk: KnowledgeChunk) -> dict:
    """Serialize a KnowledgeChunk to a response dict."""
    return {
        "knowledge_id": chunk.knowledge_id,
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "document_name": chunk.document_name,
        "category": chunk.category,
        "page_number": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text[:300] + "…" if len(chunk.text) > 300 else chunk.text,
        "keywords": chunk.keywords,
        "entities": [e.to_dict() for e in chunk.entities[:10]],  # Cap for response size
        "legal_sections": chunk.legal_sections,
        "references": chunk.references,
        "relationships": [r.to_dict() for r in chunk.relationships],
        "token_estimate": chunk.token_estimate,
        "char_count": chunk.char_count,
        "created_at": chunk.created_at.isoformat(),
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/build",
    response_model=StandardResponse,
    summary="Build OKF Knowledge Base",
    description=(
        "Scans all indexed chunk JSON files in metadata/chunks/, runs NLP extraction "
        "(entities, keywords, legal sections, references, relationships) on every chunk, "
        "and produces knowledge.json and knowledge_chunks.json in metadata/knowledge/."
    ),
)
async def build_knowledge(
    service: KnowledgeServiceDep,
    force_rebuild: bool = Query(default=True, description="Rebuild even if OKF already exists"),
) -> StandardResponse:
    """Trigger a full OKF standardization build."""
    knowledge_log.info("POST /knowledge/build | force={force}", force=force_rebuild)
    try:
        result = service.build(force_rebuild=force_rebuild)
        return StandardResponse.success(
            data={
                "total_documents": result.total_documents,
                "total_knowledge_chunks": result.total_knowledge_chunks,
                "total_entities": result.total_entities,
                "total_keywords": result.total_keywords,
                "total_references": result.total_references,
                "total_legal_sections": result.total_legal_sections,
                "total_relationships": result.total_relationships,
                "chunks_processed": result.chunks_processed,
                "build_time_ms": result.build_time_ms,
                "built_at": result.built_at.isoformat(),
            },
            message=(
                f"OKF knowledge base built: {result.total_documents} documents, "
                f"{result.total_knowledge_chunks} knowledge chunks, "
                f"{result.total_entities} entities."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        knowledge_log.error("OKF build failed | error={e}", e=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OKF build failed: {exc}",
        ) from exc


@router.get(
    "/stats",
    response_model=StandardResponse,
    summary="Knowledge Base Statistics",
    description="Returns statistics about the current OKF knowledge base.",
)
async def get_stats(service: KnowledgeServiceDep) -> StandardResponse:
    """Return knowledge base statistics."""
    stats = service.get_stats()
    return StandardResponse.success(
        data={
            "total_documents": stats.total_documents,
            "total_knowledge_chunks": stats.total_knowledge_chunks,
            "is_built": stats.is_built,
            "last_built_at": stats.last_built_at.isoformat() if stats.last_built_at else None,
            "categories": stats.categories,
        },
        message="Knowledge base statistics retrieved successfully.",
    )


@router.get(
    "/documents",
    response_model=StandardResponse,
    summary="List All Knowledge Documents",
    description="Returns summary information for all KnowledgeDocument objects in the knowledge base.",
)
async def list_documents(service: KnowledgeServiceDep) -> StandardResponse:
    """List all knowledge documents."""
    documents = service.get_all_documents()
    return StandardResponse.success(
        data={
            "documents": [_doc_to_summary(d) for d in documents],
            "total": len(documents),
        },
        message=f"Retrieved {len(documents)} knowledge documents.",
    )


@router.get(
    "/document/{doc_id}",
    response_model=StandardResponse,
    summary="Get Knowledge Document",
    description="Get the full OKF knowledge document for a given document_id.",
)
async def get_document(doc_id: str, service: KnowledgeServiceDep) -> StandardResponse:
    """Get a single knowledge document by document_id."""
    doc = service.get_document_by_id(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document for document_id '{doc_id}' not found.",
        )
    return StandardResponse.success(
        data=doc.to_dict(),
        message="Knowledge document retrieved successfully.",
    )


@router.get(
    "/chunks",
    response_model=StandardResponse,
    summary="List Knowledge Chunks (Paginated)",
    description=(
        "Returns paginated KnowledgeChunk objects from the knowledge base. "
        "Use ?page=1&size=100 for pagination. Filter by document_id with ?doc_id=..."
    ),
)
async def list_chunks(
    service: KnowledgeServiceDep,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(default=100, ge=1, le=500, description="Items per page"),
    doc_id: Optional[str] = Query(default=None, description="Filter by document_id"),
) -> StandardResponse:
    """List knowledge chunks with pagination and optional document filter."""
    chunks = service.get_chunks(doc_id=doc_id)
    total = len(chunks)
    start = (page - 1) * size
    end = start + size
    page_chunks = chunks[start:end]

    return StandardResponse.success(
        data={
            "chunks": [_chunk_to_summary(c) for c in page_chunks],
            "total": total,
            "page": page,
            "size": size,
            "total_pages": (total + size - 1) // size if total > 0 else 0,
        },
        message=f"Retrieved {len(page_chunks)} knowledge chunks (page {page}).",
    )


@router.get(
    "/chunk/{knowledge_id}",
    response_model=StandardResponse,
    summary="Get Knowledge Chunk",
    description="Retrieve a single KnowledgeChunk by its unique knowledge_id.",
)
async def get_chunk(knowledge_id: str, service: KnowledgeServiceDep) -> StandardResponse:
    """Get a single knowledge chunk by knowledge_id."""
    chunk = service.get_chunk_by_id(knowledge_id)
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge chunk '{knowledge_id}' not found.",
        )
    return StandardResponse.success(
        data=chunk.to_dict(),
        message="Knowledge chunk retrieved successfully.",
    )
