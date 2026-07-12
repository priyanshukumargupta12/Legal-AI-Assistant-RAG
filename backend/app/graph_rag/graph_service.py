"""
app/graph_rag/graph_service.py
================================
Orchestration service for the Graph RAG module.

PURPOSE:
    Coordinates all Graph RAG operations:
        1. Build (or rebuild) the legal knowledge graph from chunk metadata
        2. Load an existing graph from disk
        3. Execute graph traversal queries
        4. Expand Hybrid RAG results via graph neighbor lookup
        5. Generate graph statistics
        6. Produce D3.js visualization data

    GraphService is the single entry point for all graph operations.
    All HTTP controllers and dependency injection factories use this class.

DESIGN:
    - GraphService holds the "live" in-memory graph state (nx.DiGraph + node_map).
    - On startup, if a graph exists on disk it is loaded automatically.
    - Graph is rebuilt on explicit POST /graph-rag/build request.
    - All traversal operations delegate to GraphSearchEngine.
    - All I/O delegates to GraphRepository.
    - All visualization delegates to GraphVisualizer.

SOLID:
    Single Responsibility — orchestration only; no I/O or traversal logic.
    Dependency Inversion — depends on injected GraphRepository, GraphBuilder,
                           GraphSearchEngine, GraphVisualizer.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from app.graph_rag.graph_builder import GraphBuilder
from app.graph_rag.graph_logger import graph_log
from app.graph_rag.graph_models import (
    EdgeType,
    GraphBuildResult,
    GraphEdge,
    GraphNode,
    GraphQueryResult,
    GraphStats,
)
from app.graph_rag.graph_repository import GraphRepository
from app.graph_rag.graph_search import GraphSearchEngine
from app.graph_rag.graph_utils import compute_graph_density
from app.graph_rag.graph_visualizer import GraphVisualizer


class GraphService:
    """
    Primary orchestration service for the legal knowledge graph.

    Manages in-memory graph state and coordinates all subsystems:
    GraphBuilder (construction), GraphRepository (I/O), GraphSearchEngine
    (traversal), and GraphVisualizer (serialization).

    Constructor Args:
        repository:          Injected GraphRepository for persistence.
        chunks_dir:          Directory of indexed chunk JSON files.
        min_edge_confidence: Minimum confidence for edge inclusion.
    """

    def __init__(
        self,
        repository: GraphRepository,
        chunks_dir: Path,
        min_edge_confidence: float = 0.3,
    ) -> None:
        """
        Initialize GraphService and attempt to load an existing graph from disk.

        Args:
            repository:          GraphRepository for save/load operations.
            chunks_dir:          Path to the metadata/chunks/ directory.
            min_edge_confidence: Edge confidence threshold passed to GraphBuilder.
        """
        self._repo = repository
        self._chunks_dir = chunks_dir
        self._min_confidence = min_edge_confidence
        self._visualizer = GraphVisualizer()

        # Live in-memory state (populated on build or load)
        self._graph: Optional[nx.DiGraph] = None
        self._nodes: List[GraphNode] = []
        self._edges: List[GraphEdge] = []
        self._node_map: Dict[str, GraphNode] = {}
        self._chunk_to_node: Dict[str, str] = {}   # chunk_id → node_id
        self._search_engine: Optional[GraphSearchEngine] = None
        self._last_build_result: Optional[GraphBuildResult] = None

        # Try to load existing graph on initialization
        self._try_load_existing_graph()

        graph_log.info(
            "GraphService initialized | chunks_dir={dir} | is_built={built}",
            dir=str(chunks_dir),
            built=self.is_built,
        )

    # =========================================================================
    # STATE PROPERTY
    # =========================================================================

    @property
    def is_built(self) -> bool:
        """Return True if a graph is currently loaded in memory."""
        return self._graph is not None and self._graph.number_of_nodes() > 0

    # =========================================================================
    # PUBLIC API — BUILD
    # =========================================================================

    def build_graph(
        self,
        force_rebuild: bool = False,
        min_edge_confidence: Optional[float] = None,
    ) -> GraphBuildResult:
        """
        Build (or rebuild) the legal knowledge graph from chunk metadata.

        If force_rebuild=False and a graph already exists on disk, the existing
        graph is returned without re-running the build process.

        PIPELINE:
            1. Instantiate GraphBuilder with injected dependencies
            2. Execute GraphBuilder.build()
            3. Cache results in memory
            4. Build GraphSearchEngine from fresh graph
            5. Build chunk→node map for retrieval expansion

        Args:
            force_rebuild:       If True, rebuild even if graph already exists.
            min_edge_confidence: Override the default confidence threshold.

        Returns:
            GraphBuildResult with statistics about the built graph.
        """
        if self.is_built and not force_rebuild:
            graph_log.info("Graph already built and force_rebuild=False — skipping rebuild")
            if self._last_build_result:
                return self._last_build_result
            # Return stats from current in-memory graph
            return self._make_build_result_from_current()

        confidence = min_edge_confidence if min_edge_confidence is not None else self._min_confidence

        graph_log.info(
            "Starting graph build | force={force} | min_confidence={conf}",
            force=force_rebuild,
            conf=confidence,
        )

        builder = GraphBuilder(
            repository=self._repo,
            chunks_dir=self._chunks_dir,
            min_edge_confidence=confidence,
        )

        nodes, edges, nx_graph, build_result = builder.build()

        # Update in-memory state
        self._nodes = nodes
        self._edges = edges
        self._graph = nx_graph
        self._node_map = {n.node_id: n for n in nodes}
        self._chunk_to_node = self._build_chunk_map(nodes)
        self._search_engine = GraphSearchEngine(
            graph=nx_graph,
            node_map=self._node_map,
        )
        self._last_build_result = build_result

        graph_log.info(
            "Graph build complete | nodes={n} | edges={e}",
            n=build_result.total_nodes,
            e=build_result.total_edges,
        )

        return build_result

    # =========================================================================
    # PUBLIC API — STATISTICS
    # =========================================================================

    def get_stats(self) -> GraphStats:
        """
        Return current statistics about the in-memory graph.

        Returns:
            GraphStats with node/edge counts, type breakdowns, and density.
        """
        if not self.is_built:
            return GraphStats(is_built=False)

        node_types: Dict[str, int] = {}
        for node in self._nodes:
            ntype = node.node_type.value
            node_types[ntype] = node_types.get(ntype, 0) + 1

        edge_types: Dict[str, int] = {}
        for edge in self._edges:
            etype = edge.edge_type.value
            edge_types[etype] = edge_types.get(etype, 0) + 1

        density = compute_graph_density(
            node_count=self._graph.number_of_nodes(),
            edge_count=self._graph.number_of_edges(),
        )

        last_built = None
        if self._last_build_result:
            last_built = self._last_build_result.built_at

        return GraphStats(
            total_nodes=len(self._nodes),
            total_edges=len(self._edges),
            node_types=node_types,
            edge_types=edge_types,
            density=density,
            is_built=True,
            last_built_at=last_built,
        )

    # =========================================================================
    # PUBLIC API — NODE / EDGE ACCESS
    # =========================================================================

    def get_all_nodes(self) -> List[GraphNode]:
        """Return all nodes in the current graph."""
        return list(self._nodes)

    def get_all_edges(self) -> List[GraphEdge]:
        """Return all edges in the current graph."""
        return list(self._edges)

    def get_node_by_id(self, node_id: str) -> Optional[GraphNode]:
        """
        Retrieve a single node by its node ID.

        Args:
            node_id: Unique node identifier.

        Returns:
            GraphNode instance or None.
        """
        return self._node_map.get(node_id)

    # =========================================================================
    # PUBLIC API — TRAVERSAL (delegates to GraphSearchEngine)
    # =========================================================================

    def get_neighbors(
        self,
        node_ids: List[str],
        depth: int = 1,
        edge_types: Optional[List[EdgeType]] = None,
    ) -> GraphQueryResult:
        """
        BFS traversal from a set of node IDs up to the given depth.

        Args:
            node_ids:   Seed node IDs.
            depth:      Traversal depth (1–4).
            edge_types: Optional edge type filter.

        Returns:
            GraphQueryResult with expanded nodes and edges traversed.

        Raises:
            RuntimeError: If graph has not been built yet.
        """
        self._require_graph()
        return self._search_engine.get_neighbors(
            node_ids=node_ids, depth=depth, edge_types=edge_types
        )

    def expand_retrieval_results(
        self,
        chunk_ids: List[str],
        depth: int = 1,
    ) -> GraphQueryResult:
        """
        Expand Hybrid RAG retrieval results via graph neighbor traversal.

        Maps chunk IDs to their parent document nodes and traverses the graph
        to find related documents not in the original retrieval set.

        Args:
            chunk_ids: Chunk IDs from Hybrid RAG top-K results.
            depth:     Traversal depth for expansion.

        Returns:
            GraphQueryResult with newly discovered document nodes.
        """
        self._require_graph()
        return self._search_engine.expand_retrieval_results(
            chunk_ids=chunk_ids,
            chunk_to_node_map=self._chunk_to_node,
            depth=depth,
        )

    def get_related_documents(self, node_id: str, depth: int = 1) -> GraphQueryResult:
        """Get all documents related to a given node via any edge type."""
        self._require_graph()
        return self._search_engine.get_related_documents(node_id=node_id, depth=depth)

    def get_referenced_acts(self, node_id: str) -> GraphQueryResult:
        """Get all Acts/statutes referenced by a given document node."""
        self._require_graph()
        return self._search_engine.get_referenced_acts(node_id=node_id)

    def get_related_judgments(self, node_id: str) -> GraphQueryResult:
        """Get all court judgments cited by or citing a given document node."""
        self._require_graph()
        return self._search_engine.get_related_judgments(node_id=node_id)

    def get_related_irs_publications(self, node_id: str) -> GraphQueryResult:
        """Get all IRS Publications related to a given document node."""
        self._require_graph()
        return self._search_engine.get_related_irs_publications(node_id=node_id)

    # =========================================================================
    # PUBLIC API — VISUALIZATION
    # =========================================================================

    def get_visualization(self) -> Dict[str, Any]:
        """
        Generate a D3.js-compatible visualization of the full graph.

        Returns:
            Dict with "nodes", "links", and "metadata" keys.

        Raises:
            RuntimeError: If graph has not been built yet.
        """
        self._require_graph()
        return self._visualizer.to_d3(
            graph=self._graph,
            node_map=self._node_map,
        )

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _require_graph(self) -> None:
        """
        Assert that the graph has been built before a traversal operation.

        Raises:
            RuntimeError: If no graph is in memory.
        """
        if not self.is_built:
            raise RuntimeError(
                "Knowledge graph has not been built. "
                "Call POST /api/v1/graph-rag/build first."
            )

    def _try_load_existing_graph(self) -> None:
        """
        Attempt to load a persisted graph from disk on service initialization.

        Silently skips if no graph files exist yet.
        """
        if not self._repo.graph_exists():
            graph_log.info("No persisted graph found — will build on first request")
            return

        try:
            nodes = self._repo.load_nodes()
            edges = self._repo.load_edges()
            nx_graph = self._repo.load_graph()

            if nx_graph is None:
                graph_log.warning("graph.json exists but could not be loaded")
                return

            self._nodes = nodes
            self._edges = edges
            self._graph = nx_graph
            self._node_map = {n.node_id: n for n in nodes}
            self._chunk_to_node = self._build_chunk_map(nodes)
            self._search_engine = GraphSearchEngine(
                graph=nx_graph,
                node_map=self._node_map,
            )

            graph_log.info(
                "Restored graph from disk | nodes={n} | edges={e}",
                n=len(nodes),
                e=len(edges),
            )
        except Exception as exc:  # noqa: BLE001
            graph_log.error(
                "Failed to load persisted graph | error={e}",
                e=str(exc),
            )

    def _build_chunk_map(self, nodes: List[GraphNode]) -> Dict[str, str]:
        """
        Build a reverse mapping from chunk_id → node_id.

        Used by expand_retrieval_results() to resolve Hybrid RAG chunk IDs
        to their parent document node IDs.

        Args:
            nodes: All GraphNode instances (with populated chunk_ids list).

        Returns:
            Dict mapping chunk_id strings to node_id strings.
        """
        mapping: Dict[str, str] = {}
        for node in nodes:
            for chunk_id in node.chunk_ids:
                mapping[chunk_id] = node.node_id
        return mapping

    def _make_build_result_from_current(self) -> GraphBuildResult:
        """
        Build a GraphBuildResult from the current in-memory graph state.

        Used when graph already exists but last_build_result is None (e.g. loaded from disk).

        Returns:
            GraphBuildResult populated from current nodes/edges.
        """
        nodes_by_type: Dict[str, int] = {}
        for n in self._nodes:
            ntype = n.node_type.value
            nodes_by_type[ntype] = nodes_by_type.get(ntype, 0) + 1

        edges_by_type: Dict[str, int] = {}
        for e in self._edges:
            etype = e.edge_type.value
            edges_by_type[etype] = edges_by_type.get(etype, 0) + 1

        return GraphBuildResult(
            total_nodes=len(self._nodes),
            total_edges=len(self._edges),
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
        )
