"""
app/graph_rag/graph_search.py
===============================
Graph traversal and query engine for the Graph RAG module.

PURPOSE:
    Implements all read-only graph traversal algorithms:
        - BFS neighbor expansion
        - Direct neighbor lookup
        - Edge-type filtered queries
        - Related document retrieval by relationship class

    GraphSearchEngine consumes a pre-built NetworkX DiGraph and a lookup map
    of node_id → GraphNode. It is stateless between calls.

DESIGN:
    - All traversal methods are synchronous and read-only.
    - BFS depth is capped at MAX_TRAVERSAL_DEPTH to prevent graph explosion.
    - Edge type filters narrow traversal to specific relationship types.
    - Every public method is self-contained (full input → full output).

SOLID:
    Single Responsibility — graph traversal only; no I/O, no persistence.
    Dependency Inversion — depends on nx.DiGraph abstraction, not file system.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Dict, List, Optional, Set

import networkx as nx

from app.graph_rag.graph_logger import graph_log
from app.graph_rag.graph_models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphQueryResult,
    NodeType,
)

# Maximum BFS traversal depth cap (safety limit)
MAX_TRAVERSAL_DEPTH: int = 4


class GraphSearchEngine:
    """
    Read-only graph traversal engine for the legal knowledge graph.

    Accepts a pre-built NetworkX DiGraph and provides multiple query
    patterns for retrieving related documents via typed relationship edges.

    Constructor Args:
        graph:    Populated NetworkX DiGraph.
        node_map: Mapping from node_id → GraphNode domain object.
    """

    def __init__(
        self,
        graph: nx.DiGraph,
        node_map: Dict[str, GraphNode],
    ) -> None:
        """
        Initialize the search engine with a built graph.

        Args:
            graph:    NetworkX DiGraph (must be pre-built).
            node_map: Dict mapping node_id → GraphNode for data access.
        """
        self._graph = graph
        self._node_map = node_map

        graph_log.info(
            "GraphSearchEngine initialized | nodes={n} | edges={e}",
            n=graph.number_of_nodes(),
            e=graph.number_of_edges(),
        )

    # =========================================================================
    # PUBLIC API — TRAVERSAL
    # =========================================================================

    def get_neighbors(
        self,
        node_ids: List[str],
        depth: int = 1,
        edge_types: Optional[List[EdgeType]] = None,
    ) -> GraphQueryResult:
        """
        BFS traversal from a set of seed nodes up to the given depth.

        Returns all nodes reachable within `depth` hops, along with the
        edges traversed to reach them. Excludes the seed nodes themselves
        from the result set.

        Args:
            node_ids:   Seed node IDs to start traversal from.
            depth:      Maximum BFS depth (capped at MAX_TRAVERSAL_DEPTH).
            edge_types: Optional filter — only traverse edges of these types.

        Returns:
            GraphQueryResult with expanded nodes and traversed edges.
        """
        start_time = time.perf_counter()
        depth = min(depth, MAX_TRAVERSAL_DEPTH)
        edge_type_values: Optional[Set[str]] = (
            {et.value for et in edge_types} if edge_types else None
        )

        graph_log.info(
            "BFS traversal | seeds={seeds} | depth={d} | edge_filter={ef}",
            seeds=node_ids,
            d=depth,
            ef=[et.value for et in edge_types] if edge_types else "all",
        )

        visited_ids: Set[str] = set(node_ids)
        expanded_node_ids: Set[str] = set()
        traversed_edge_data: List[dict] = []

        # BFS queue: (node_id, current_depth)
        queue: deque = deque((nid, 0) for nid in node_ids if nid in self._graph)

        while queue:
            current_id, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            # Traverse both outgoing and incoming edges
            successors = self._graph.successors(current_id)
            predecessors = self._graph.predecessors(current_id)

            for neighbor_id in list(successors) + list(predecessors):
                # Get edge data (try both directions)
                edge_data = (
                    self._graph.edges.get((current_id, neighbor_id))
                    or self._graph.edges.get((neighbor_id, current_id))
                    or {}
                )

                # Apply edge type filter
                if edge_type_values and edge_data.get("edge_type") not in edge_type_values:
                    continue

                if neighbor_id not in visited_ids:
                    visited_ids.add(neighbor_id)
                    expanded_node_ids.add(neighbor_id)
                    traversed_edge_data.append(edge_data)
                    queue.append((neighbor_id, current_depth + 1))

        # Resolve expanded node IDs to GraphNode objects
        expanded_nodes = [
            self._node_map[nid]
            for nid in expanded_node_ids
            if nid in self._node_map
        ]

        # Reconstruct GraphEdge objects from edge data dicts
        traversed_edges = self._build_edge_objects(traversed_edge_data)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        graph_log.info(
            "BFS complete | expanded={exp} | edges={e} | time={t:.2f}ms",
            exp=len(expanded_nodes),
            e=len(traversed_edges),
            t=elapsed_ms,
        )

        return GraphQueryResult(
            query_node_ids=node_ids,
            expanded_nodes=expanded_nodes,
            edges_traversed=traversed_edges,
            depth=depth,
            traversal_time_ms=round(elapsed_ms, 2),
        )

    def get_related_documents(
        self,
        node_id: str,
        depth: int = 1,
    ) -> GraphQueryResult:
        """
        Retrieve all documents directly related to a given node.

        Convenience wrapper around get_neighbors() with depth=1 by default.

        Args:
            node_id: Source document node ID.
            depth:   Traversal depth (default: 1 for direct neighbors only).

        Returns:
            GraphQueryResult with all directly related document nodes.
        """
        return self.get_neighbors(node_ids=[node_id], depth=depth)

    def get_referenced_acts(self, node_id: str) -> GraphQueryResult:
        """
        Retrieve all Act/statute documents referenced by the given node.

        Filters traversal to REFERS_TO and REFERENCES_SECTION edge types only,
        then further filters results to nodes of type ACT.

        Args:
            node_id: Source document node ID.

        Returns:
            GraphQueryResult containing only referenced Act nodes.
        """
        result = self.get_neighbors(
            node_ids=[node_id],
            depth=2,
            edge_types=[EdgeType.REFERS_TO, EdgeType.REFERENCES_SECTION],
        )
        # Filter expanded nodes to ACT type only
        result.expanded_nodes = [
            n for n in result.expanded_nodes if n.node_type == NodeType.ACT
        ]
        return result

    def get_related_judgments(self, node_id: str) -> GraphQueryResult:
        """
        Retrieve all court judgments cited by or citing the given document.

        Filters traversal to CITES and OVERRULES edge types, then filters
        results to COURT_JUDGMENT node type.

        Args:
            node_id: Source document node ID.

        Returns:
            GraphQueryResult containing only court judgment nodes.
        """
        result = self.get_neighbors(
            node_ids=[node_id],
            depth=2,
            edge_types=[EdgeType.CITES, EdgeType.OVERRULES],
        )
        result.expanded_nodes = [
            n for n in result.expanded_nodes if n.node_type == NodeType.COURT_JUDGMENT
        ]
        return result

    def get_related_irs_publications(self, node_id: str) -> GraphQueryResult:
        """
        Retrieve all IRS Publications and tax documents related to the given node.

        Filters traversal to EXPLAINS and REFERS_TO edge types, then filters
        results to TAX_DOCUMENT node type.

        Args:
            node_id: Source document node ID.

        Returns:
            GraphQueryResult containing only tax document nodes.
        """
        result = self.get_neighbors(
            node_ids=[node_id],
            depth=2,
            edge_types=[EdgeType.EXPLAINS, EdgeType.REFERS_TO],
        )
        result.expanded_nodes = [
            n for n in result.expanded_nodes if n.node_type == NodeType.TAX_DOCUMENT
        ]
        return result

    def expand_retrieval_results(
        self,
        chunk_ids: List[str],
        chunk_to_node_map: Dict[str, str],
        depth: int = 1,
    ) -> GraphQueryResult:
        """
        Expand Hybrid RAG results by resolving chunks to nodes and traversing.

        This is the primary integration point between Hybrid RAG and Graph RAG.
        It takes the chunk_ids from Hybrid RAG top-K results, maps them to
        their parent document nodes, then traverses the graph to find related
        documents that were NOT in the original retrieval set.

        Args:
            chunk_ids:         List of chunk_ids from Hybrid RAG top-K results.
            chunk_to_node_map: Mapping from chunk_id → node_id (built at graph build time).
            depth:             Traversal depth for expansion.

        Returns:
            GraphQueryResult with newly discovered related document nodes.
        """
        # Resolve chunk IDs to node IDs
        resolved_node_ids = list({
            chunk_to_node_map[cid]
            for cid in chunk_ids
            if cid in chunk_to_node_map
        })

        graph_log.info(
            "Expanding retrieval results | chunks={nc} | resolved_nodes={nn}",
            nc=len(chunk_ids),
            nn=len(resolved_node_ids),
        )

        if not resolved_node_ids:
            return GraphQueryResult(
                query_node_ids=[],
                expanded_nodes=[],
                edges_traversed=[],
                depth=depth,
            )

        return self.get_neighbors(node_ids=resolved_node_ids, depth=depth)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """
        Retrieve a single GraphNode by its node ID.

        Args:
            node_id: Node ID to look up.

        Returns:
            GraphNode instance or None if not found.
        """
        return self._node_map.get(node_id)

    def list_all_nodes(self) -> List[GraphNode]:
        """Return all nodes in the graph as a list."""
        return list(self._node_map.values())

    def list_all_edges(
        self,
        source_node_map: Dict[str, GraphNode],
    ) -> List[GraphEdge]:
        """
        Return all edges in the graph as GraphEdge objects.

        Args:
            source_node_map: node_id → GraphNode map (same as self._node_map).

        Returns:
            List of all GraphEdge objects reconstructed from NetworkX edge data.
        """
        edge_objects: List[GraphEdge] = []
        for src, tgt, data in self._graph.edges(data=True):
            edge_objects.append(
                GraphEdge(
                    edge_id=data.get("edge_id", f"{src}→{tgt}"),
                    source_id=src,
                    target_id=tgt,
                    edge_type=EdgeType(data.get("edge_type", "REFERS_TO")),
                    weight=float(data.get("weight", 1.0)),
                    confidence=float(data.get("confidence", 1.0)),
                    detected_pattern=data.get("detected_pattern", ""),
                    occurrence_count=int(data.get("occurrence_count", 1)),
                )
            )
        return edge_objects

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _build_edge_objects(self, edge_data_list: List[dict]) -> List[GraphEdge]:
        """
        Convert raw NetworkX edge attribute dicts to GraphEdge domain objects.

        Args:
            edge_data_list: List of edge attribute dicts from nx.edges(data=True).

        Returns:
            List of GraphEdge objects.
        """
        edges: List[GraphEdge] = []
        for data in edge_data_list:
            if not data:
                continue
            try:
                edges.append(
                    GraphEdge(
                        edge_id=data.get("edge_id", ""),
                        source_id=data.get("source_id", ""),
                        target_id=data.get("target_id", ""),
                        edge_type=EdgeType(data.get("edge_type", "REFERS_TO")),
                        weight=float(data.get("weight", 1.0)),
                        confidence=float(data.get("confidence", 1.0)),
                        detected_pattern=data.get("detected_pattern", ""),
                        occurrence_count=int(data.get("occurrence_count", 1)),
                    )
                )
            except (ValueError, KeyError):
                pass
        return edges
