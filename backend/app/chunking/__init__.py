"""
app/chunking/__init__.py
=========================
Intelligent Chunking Module — public interface.

PURPOSE:
    Re-exports the stable public surface of the Chunking Module.
    Callers (e.g., the main application, ingestion pipeline, tests) should
    import from this module rather than directly from submodules. This keeps
    the internal file structure free to change without breaking call sites.

PUBLIC EXPORTS:
    chunk_router              — FastAPI APIRouter for HTTP endpoints.
    DocumentChunk             — Immutable domain entity for a single chunk.
    ChunkStatistics           — Per-document chunking statistics.
    GlobalChunkStats          — Cross-document batch statistics.
    ChunkRepository           — Abstract repository interface.
    FileSystemChunkRepository — File-system repository implementation.
    ChunkingService           — Primary service for the chunking pipeline.
"""

from __future__ import annotations

from app.chunking.chunk_controller import router as chunk_router
from app.chunking.chunk_models import ChunkStatistics, DocumentChunk, GlobalChunkStats
from app.chunking.chunk_repository import ChunkRepository, FileSystemChunkRepository
from app.chunking.chunk_service import ChunkingService

__all__ = [
    "chunk_router",
    "DocumentChunk",
    "ChunkStatistics",
    "GlobalChunkStats",
    "ChunkRepository",
    "FileSystemChunkRepository",
    "ChunkingService",
]
