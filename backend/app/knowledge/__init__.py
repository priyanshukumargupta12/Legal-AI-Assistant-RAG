"""
app/knowledge/__init__.py
==========================
Public API surface for the OKF Knowledge Standardization Module.

Exports the primary classes and types that external modules
(routes, DI factories, tests) should import from this package.

Usage:
    from app.knowledge import KnowledgeService, KnowledgeRepository
    from app.knowledge import KnowledgeChunk, KnowledgeDocument
    from app.knowledge import EntityType, NamedEntity
"""

from __future__ import annotations

from app.knowledge.knowledge_builder import KnowledgeBuilder
from app.knowledge.knowledge_models import (
    EntityType,
    KnowledgeBuildResult,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeRelation,
    KnowledgeStats,
    NamedEntity,
)
from app.knowledge.knowledge_repository import KnowledgeRepository
from app.knowledge.knowledge_service import KnowledgeService

__all__ = [
    "KnowledgeService",
    "KnowledgeBuilder",
    "KnowledgeRepository",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeBuildResult",
    "KnowledgeRelation",
    "KnowledgeStats",
    "NamedEntity",
    "EntityType",
]
