"""
app/graph_rag/graph_schemas.py
================================
Pydantic v2 request and response schemas for Graph RAG HTTP endpoints.

PURPOSE:
    Defines all validated input/output shapes for the FastAPI controller.
    Keeps domain models (dataclasses) separate from HTTP schemas (Pydantic).

DESIGN:
    - All request models validate inputs at the HTTP boundary.
    - All response models guarantee serializable output.
    - Schema names follow the pattern: <Action><Request|Response>.

SOLID: Single Responsibility — schema validation only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class GraphBuildRequest(BaseModel):
    """
    Request body for POST /graph-rag/build.

    Triggers a full graph construction from indexed chunk metadata files.
    """

    force_rebuild: bool = Field(
        default=False,
        description="Force rebuild even if a graph already exists on disk.",
    )
    min_edge_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for an edge to be included.",
    )


class GraphNeighborRequest(BaseModel):
    """
    Request body for POST /graph-rag/neighbors.

    Retrieves all graph neighbors for a set of document node IDs.
    """

    node_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of document node IDs to find neighbors for.",
    )
    depth: int = Field(
        default=1,
        ge=1,
        le=4,
        description="BFS traversal depth (1 = direct neighbors, 2 = two hops, etc.).",
    )
    edge_types: Optional[List[str]] = Field(
        default=None,
        description="Optional list of EdgeType values to filter traversal by. If None, all edges used.",
    )


class GraphExpandRequest(BaseModel):
    """
    Request body for POST /graph-rag/expand.

    Expands a list of Hybrid RAG result chunks by resolving their parent
    document nodes in the graph and returning related documents.
    """

    chunk_ids: List[str] = Field(
        ...,
        min_length=1,
        description="Chunk IDs from Hybrid RAG results to expand via graph traversal.",
    )
    depth: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Graph traversal depth for expansion.",
    )


class GraphQueryRequest(BaseModel):
    """
    Request body for POST /graph-rag/query.

    Finds nodes related to a given document by ID, with optional relationship type filter.
    """

    node_id: str = Field(..., description="Source document node ID to query from.")
    relation: Optional[str] = Field(
        default=None,
        description="Optional EdgeType name to filter (e.g. 'CITES', 'REFERS_TO').",
    )
    depth: int = Field(default=1, ge=1, le=3, description="Traversal depth.")


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class GraphNodeSchema(BaseModel):
    """
    Serialized representation of a single graph node for HTTP responses.
    """

    node_id: str
    node_type: str
    document_name: str
    category: str
    page_count: int
    summary: str
    chunk_count: int
    created_at: str


class GraphEdgeSchema(BaseModel):
    """
    Serialized representation of a single graph edge for HTTP responses.
    """

    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    weight: float
    confidence: float
    detected_pattern: str
    occurrence_count: int


class GraphBuildResponse(BaseModel):
    """
    Response returned after a graph build operation.
    """

    total_nodes: int
    total_edges: int
    nodes_by_type: Dict[str, int]
    edges_by_type: Dict[str, int]
    build_time_ms: float
    chunks_scanned: int
    patterns_matched: int
    built_at: str


class GraphStatsResponse(BaseModel):
    """
    Response for the graph statistics endpoint.
    """

    total_nodes: int
    total_edges: int
    node_types: Dict[str, int]
    edge_types: Dict[str, int]
    density: float
    is_built: bool
    last_built_at: Optional[str]


class GraphNeighborResponse(BaseModel):
    """
    Response for the graph neighbor traversal endpoint.
    """

    query_node_ids: List[str]
    depth: int
    expanded_nodes: List[GraphNodeSchema]
    edges_traversed: List[GraphEdgeSchema]
    traversal_time_ms: float
    total_neighbors: int


class GraphExpandResponse(BaseModel):
    """
    Response for the Hybrid RAG expansion endpoint.
    """

    original_chunk_ids: List[str]
    resolved_node_ids: List[str]
    expanded_documents: List[GraphNodeSchema]
    expansion_edges: List[GraphEdgeSchema]
    traversal_time_ms: float


class GraphVisualizationResponse(BaseModel):
    """
    D3.js-compatible graph visualization payload.

    The frontend can feed this directly into a D3-force / vis.js renderer.
    """

    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    metadata: Dict[str, Any]
