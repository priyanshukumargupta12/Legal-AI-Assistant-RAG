"""
app/graph_rag/__init__.py
==========================
Public API surface for the Graph RAG module.

Exports the primary classes and types that external modules (routes,
dependency injection, tests) should import from this package.

Usage:
    from app.graph_rag import GraphService, GraphRepository, GraphBuilder
    from app.graph_rag import GraphNode, GraphEdge, NodeType, EdgeType
"""

from __future__ import annotations

from app.graph_rag.graph_builder import GraphBuilder
from app.graph_rag.graph_models import (
    EdgeType,
    GraphBuildResult,
    GraphEdge,
    GraphNode,
    GraphQueryResult,
    GraphStats,
    NodeType,
)
from app.graph_rag.graph_repository import GraphRepository
from app.graph_rag.graph_search import GraphSearchEngine
from app.graph_rag.graph_service import GraphService
from app.graph_rag.graph_visualizer import GraphVisualizer

__all__ = [
    "GraphService",
    "GraphBuilder",
    "GraphRepository",
    "GraphSearchEngine",
    "GraphVisualizer",
    "GraphNode",
    "GraphEdge",
    "GraphBuildResult",
    "GraphQueryResult",
    "GraphStats",
    "NodeType",
    "EdgeType",
]
