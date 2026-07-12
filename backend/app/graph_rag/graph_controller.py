"""
app/graph_rag/graph_controller.py
====================================
FastAPI router (HTTP controller) for Graph RAG endpoints.

PURPOSE:
    Thin HTTP adapter layer between FastAPI and GraphService.
    Translates HTTP requests into service calls and service outputs into
    standardized HTTP responses. Contains zero business logic.

ENDPOINTS:
    POST /graph-rag/build        — Build the knowledge graph from chunk data
    GET  /graph-rag/stats        — Graph statistics (nodes, edges, density)
    GET  /graph-rag/nodes        — List all graph nodes
    GET  /graph-rag/edges        — List all graph edges
    GET  /graph-rag/node/{id}    — Get a single node by ID
    POST /graph-rag/neighbors    — BFS neighbor traversal for given node IDs
    POST /graph-rag/expand       — Expand Hybrid RAG chunk IDs via graph
    POST /graph-rag/query        — Query related documents for a single node
    GET  /graph-rag/visualize    — D3.js-compatible visualization JSON

DESIGN:
    - All dependency injection via FastAPI Depends().
    - Uniform StandardResponse envelope for all endpoints.
    - Errors translated to structured HTTP 400/404/500 responses.

SOLID: Single Responsibility — HTTP translation only.
"""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.responses.standard_response import StandardResponse
from app.graph_rag.graph_logger import graph_log
from app.graph_rag.graph_models import EdgeType, NodeType
from app.graph_rag.graph_schemas import (
    GraphBuildRequest,
    GraphBuildResponse,
    GraphEdgeSchema,
    GraphExpandRequest,
    GraphNeighborRequest,
    GraphNeighborResponse,
    GraphNodeSchema,
    GraphQueryRequest,
    GraphStatsResponse,
    GraphVisualizationResponse,
)
from app.graph_rag.graph_service import GraphService

router = APIRouter(prefix="/graph-rag", tags=["Graph RAG"])


# =============================================================================
# DEPENDENCY TYPE ALIAS (injected by services.py factory)
# =============================================================================

# GraphServiceDep is resolved via FastAPI DI — the factory is registered
# in app/api/dependencies/services.py as get_graph_service().
from app.api.dependencies.services import get_graph_service  # noqa: E402
GraphServiceDep = Annotated[GraphService, Depends(get_graph_service)]


# =============================================================================
# HELPER — DOMAIN MODEL → SCHEMA CONVERTERS
# =============================================================================

def _node_to_schema(node) -> GraphNodeSchema:
    """Convert a GraphNode domain object to its HTTP response schema."""
    return GraphNodeSchema(
        node_id=node.node_id,
        node_type=node.node_type.value,
        document_name=node.document_name,
        category=node.category,
        page_count=node.page_count,
        summary=node.summary,
        chunk_count=len(node.chunk_ids),
        created_at=node.created_at.isoformat(),
    )


def _edge_to_schema(edge) -> GraphEdgeSchema:
    """Convert a GraphEdge domain object to its HTTP response schema."""
    return GraphEdgeSchema(
        edge_id=edge.edge_id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        edge_type=edge.edge_type.value,
        weight=edge.weight,
        confidence=edge.confidence,
        detected_pattern=edge.detected_pattern,
        occurrence_count=edge.occurrence_count,
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/build",
    response_model=StandardResponse,
    summary="Build Knowledge Graph",
    description=(
        "Scans indexed chunk metadata files, detects cross-document legal references "
        "(IRC §, CFR, case citations, Act names, Pub. numbers), and constructs a "
        "directed knowledge graph. Persists nodes.json, edges.json, graph.json to disk."
    ),
)
async def build_graph(
    request: GraphBuildRequest,
    service: GraphServiceDep,
) -> StandardResponse:
    """Trigger a full graph build from chunk metadata."""
    graph_log.info(
        "POST /build | force={force} | min_conf={conf}",
        force=request.force_rebuild,
        conf=request.min_edge_confidence,
    )
    try:
        result = service.build_graph(
            force_rebuild=request.force_rebuild,
            min_edge_confidence=request.min_edge_confidence,
        )
        return StandardResponse.success(
            data=GraphBuildResponse(
                total_nodes=result.total_nodes,
                total_edges=result.total_edges,
                nodes_by_type=result.nodes_by_type,
                edges_by_type=result.edges_by_type,
                build_time_ms=result.build_time_ms,
                chunks_scanned=result.chunks_scanned,
                patterns_matched=result.patterns_matched,
                built_at=result.built_at.isoformat(),
            ).model_dump(),
            message=(
                f"Knowledge graph built successfully: "
                f"{result.total_nodes} nodes, {result.total_edges} edges."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        graph_log.error("Graph build failed | error={e}", e=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph build failed: {exc}",
        ) from exc


@router.get(
    "/stats",
    response_model=StandardResponse,
    summary="Graph Statistics",
    description="Returns current knowledge graph statistics including node/edge counts, type distributions, and graph density.",
)
async def get_stats(service: GraphServiceDep) -> StandardResponse:
    """Return graph statistics."""
    stats = service.get_stats()
    return StandardResponse.success(
        data=GraphStatsResponse(
            total_nodes=stats.total_nodes,
            total_edges=stats.total_edges,
            node_types=stats.node_types,
            edge_types=stats.edge_types,
            density=stats.density,
            is_built=stats.is_built,
            last_built_at=stats.last_built_at.isoformat() if stats.last_built_at else None,
        ).model_dump(),
        message="Graph statistics retrieved successfully.",
    )


@router.get(
    "/nodes",
    response_model=StandardResponse,
    summary="List All Graph Nodes",
    description="Returns all document nodes in the knowledge graph.",
)
async def list_nodes(service: GraphServiceDep) -> StandardResponse:
    """Return all graph nodes."""
    nodes = service.get_all_nodes()
    return StandardResponse.success(
        data={
            "nodes": [_node_to_schema(n).model_dump() for n in nodes],
            "total": len(nodes),
        },
        message=f"Retrieved {len(nodes)} graph nodes.",
    )


@router.get(
    "/edges",
    response_model=StandardResponse,
    summary="List All Graph Edges",
    description="Returns all directed relationship edges in the knowledge graph.",
)
async def list_edges(service: GraphServiceDep) -> StandardResponse:
    """Return all graph edges."""
    edges = service.get_all_edges()
    return StandardResponse.success(
        data={
            "edges": [_edge_to_schema(e).model_dump() for e in edges],
            "total": len(edges),
        },
        message=f"Retrieved {len(edges)} graph edges.",
    )


@router.get(
    "/node/{node_id}",
    response_model=StandardResponse,
    summary="Get Node by ID",
    description="Retrieve a single graph node by its unique node ID.",
)
async def get_node(node_id: str, service: GraphServiceDep) -> StandardResponse:
    """Retrieve a single node by node_id."""
    node = service.get_node_by_id(node_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found in graph.",
        )
    return StandardResponse.success(
        data=_node_to_schema(node).model_dump(),
        message="Node retrieved successfully.",
    )


@router.post(
    "/neighbors",
    response_model=StandardResponse,
    summary="Graph Neighbor Traversal",
    description=(
        "BFS traversal from a set of seed document node IDs. Returns all nodes "
        "reachable within the specified depth, along with the edges traversed. "
        "Optionally filter traversal to specific edge types."
    ),
)
async def get_neighbors(
    request: GraphNeighborRequest,
    service: GraphServiceDep,
) -> StandardResponse:
    """BFS neighbor traversal from seed nodes."""
    try:
        edge_types = None
        if request.edge_types:
            try:
                edge_types = [EdgeType(et) for et in request.edge_types]
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid edge_type value: {exc}",
                ) from exc

        result = service.get_neighbors(
            node_ids=request.node_ids,
            depth=request.depth,
            edge_types=edge_types,
        )
        return StandardResponse.success(
            data=GraphNeighborResponse(
                query_node_ids=result.query_node_ids,
                depth=result.depth,
                expanded_nodes=[_node_to_schema(n).model_dump() for n in result.expanded_nodes],
                edges_traversed=[_edge_to_schema(e).model_dump() for e in result.edges_traversed],
                traversal_time_ms=result.traversal_time_ms,
                total_neighbors=len(result.expanded_nodes),
            ).model_dump(),
            message=f"Found {len(result.expanded_nodes)} related documents via graph traversal.",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/expand",
    response_model=StandardResponse,
    summary="Expand Hybrid RAG Results via Graph",
    description=(
        "Post-retrieval expansion: takes chunk IDs from Hybrid RAG results, resolves "
        "them to document nodes, and traverses the graph to surface related documents "
        "not present in the original retrieval set. Enriches RAG context."
    ),
)
async def expand_retrieval(
    request: GraphExpandRequest,
    service: GraphServiceDep,
) -> StandardResponse:
    """Expand Hybrid RAG chunk IDs via graph traversal."""
    try:
        result = service.expand_retrieval_results(
            chunk_ids=request.chunk_ids,
            depth=request.depth,
        )
        return StandardResponse.success(
            data={
                "original_chunk_ids": request.chunk_ids,
                "resolved_node_ids": result.query_node_ids,
                "expanded_documents": [_node_to_schema(n).model_dump() for n in result.expanded_nodes],
                "expansion_edges": [_edge_to_schema(e).model_dump() for e in result.edges_traversed],
                "traversal_time_ms": result.traversal_time_ms,
                "total_expanded": len(result.expanded_nodes),
            },
            message=f"Expanded {len(request.chunk_ids)} chunk(s) → {len(result.expanded_nodes)} related documents.",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/query",
    response_model=StandardResponse,
    summary="Query Related Documents",
    description=(
        "Query documents related to a single node. Optionally filter by "
        "relationship type (e.g. 'CITES', 'EXPLAINS', 'REFERS_TO')."
    ),
)
async def query_related(
    request: GraphQueryRequest,
    service: GraphServiceDep,
) -> StandardResponse:
    """Query documents related to a given node via optional edge type filter."""
    try:
        edge_filter = None
        if request.relation:
            try:
                edge_filter = [EdgeType(request.relation)]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid relation type: '{request.relation}'. "
                           f"Valid values: {[e.value for e in EdgeType]}",
                )

        result = service.get_neighbors(
            node_ids=[request.node_id],
            depth=request.depth,
            edge_types=edge_filter,
        )
        return StandardResponse.success(
            data={
                "node_id": request.node_id,
                "relation_filter": request.relation,
                "depth": request.depth,
                "related_documents": [_node_to_schema(n).model_dump() for n in result.expanded_nodes],
                "edges": [_edge_to_schema(e).model_dump() for e in result.edges_traversed],
                "total": len(result.expanded_nodes),
                "traversal_time_ms": result.traversal_time_ms,
            },
            message=f"Found {len(result.expanded_nodes)} related documents.",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/visualize",
    response_model=StandardResponse,
    summary="Interactive Graph Visualization",
    description=(
        "Returns a D3.js / vis.js / Cytoscape.js compatible JSON representation "
        "of the full knowledge graph with color-coded nodes and weighted edges. "
        "Feed directly into a frontend graph renderer."
    ),
)
async def get_visualization(service: GraphServiceDep) -> StandardResponse:
    """Return D3.js-compatible visualization data for the full graph."""
    try:
        viz_data = service.get_visualization()
        return StandardResponse.success(
            data=viz_data,
            message=(
                f"Graph visualization generated: "
                f"{viz_data['metadata']['total_nodes']} nodes, "
                f"{viz_data['metadata']['total_edges']} edges."
            ),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
