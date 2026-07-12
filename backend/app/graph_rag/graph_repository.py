"""
app/graph_rag/graph_repository.py
==================================
Persistence layer for the Graph RAG Knowledge Graph.

PURPOSE:
    Implements all graph storage and retrieval I/O operations.
    Reads and writes the knowledge graph to three JSON files:
        - nodes.json  → all GraphNode objects
        - edges.json  → all GraphEdge objects
        - graph.json  → full NetworkX adjacency representation

    This is the ONLY class that touches the file system for graph data.
    All other classes depend on GraphRepository via constructor injection.

DESIGN:
    - Repository Pattern: GraphRepository is the single I/O boundary.
    - Uses atomic write (write to temp file, rename) to prevent corruption.
    - NetworkX graph is serialized using node_link_data for portability.

SOLID:
    Single Responsibility — file I/O only; no graph logic.
    Dependency Inversion — GraphService depends on GraphRepository interface.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import networkx as nx

from app.graph_rag.graph_logger import graph_log
from app.graph_rag.graph_models import (
    GraphEdge,
    GraphNode,
    EdgeType,
    NodeType,
)


class GraphRepository:
    """
    File-system backed persistence for the legal knowledge graph.

    Manages three JSON files:
        nodes.json  — serialized GraphNode objects
        edges.json  — serialized GraphEdge objects
        graph.json  — NetworkX node-link format for full graph restoration

    Constructor Args:
        storage_dir: Absolute path to the graph storage directory.
    """

    def __init__(self, storage_dir: Path) -> None:
        """
        Initialize GraphRepository and ensure storage directory exists.

        Args:
            storage_dir: Directory where graph JSON files are written.
        """
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._nodes_path = self._storage_dir / "nodes.json"
        self._edges_path = self._storage_dir / "edges.json"
        self._graph_path = self._storage_dir / "graph.json"

        graph_log.info(
            "GraphRepository initialized | storage={dir}",
            dir=str(self._storage_dir),
        )

    # =========================================================================
    # SAVE OPERATIONS
    # =========================================================================

    def save_nodes(self, nodes: List[GraphNode]) -> None:
        """
        Persist all GraphNode objects to nodes.json.

        Args:
            nodes: List of GraphNode instances to serialize.
        """
        data = [node.to_dict() for node in nodes]
        self._atomic_write(self._nodes_path, data)
        graph_log.info(
            "Saved nodes | count={count} | path={path}",
            count=len(nodes),
            path=str(self._nodes_path),
        )

    def save_edges(self, edges: List[GraphEdge]) -> None:
        """
        Persist all GraphEdge objects to edges.json.

        Args:
            edges: List of GraphEdge instances to serialize.
        """
        data = [edge.to_dict() for edge in edges]
        self._atomic_write(self._edges_path, data)
        graph_log.info(
            "Saved edges | count={count} | path={path}",
            count=len(edges),
            path=str(self._edges_path),
        )

    def save_graph(self, graph: nx.DiGraph) -> None:
        """
        Persist the full NetworkX DiGraph to graph.json using node_link_data.

        Args:
            graph: NetworkX directed graph to serialize.
        """
        data = nx.node_link_data(graph)
        self._atomic_write(self._graph_path, data)
        graph_log.info(
            "Saved graph | nodes={n} | edges={e} | path={path}",
            n=graph.number_of_nodes(),
            e=graph.number_of_edges(),
            path=str(self._graph_path),
        )

    def save_all(
        self,
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        graph: nx.DiGraph,
    ) -> None:
        """
        Persist nodes, edges, and full graph in one transactional operation.

        Args:
            nodes: All GraphNode objects.
            edges: All GraphEdge objects.
            graph: The constructed NetworkX DiGraph.
        """
        self.save_nodes(nodes)
        self.save_edges(edges)
        self.save_graph(graph)
        graph_log.info(
            "All graph data saved | nodes={n} | edges={e}",
            n=len(nodes),
            e=len(edges),
        )

    # =========================================================================
    # LOAD OPERATIONS
    # =========================================================================

    def load_nodes(self) -> List[GraphNode]:
        """
        Load all GraphNode objects from nodes.json.

        Returns:
            List of deserialized GraphNode instances.
            Empty list if the file does not exist.
        """
        if not self._nodes_path.exists():
            graph_log.warning("nodes.json not found — graph not yet built")
            return []

        raw = self._read_json(self._nodes_path)
        nodes = [GraphNode.from_dict(item) for item in raw]
        graph_log.info("Loaded nodes | count={count}", count=len(nodes))
        return nodes

    def load_edges(self) -> List[GraphEdge]:
        """
        Load all GraphEdge objects from edges.json.

        Returns:
            List of deserialized GraphEdge instances.
            Empty list if the file does not exist.
        """
        if not self._edges_path.exists():
            graph_log.warning("edges.json not found — graph not yet built")
            return []

        raw = self._read_json(self._edges_path)
        edges = [GraphEdge.from_dict(item) for item in raw]
        graph_log.info("Loaded edges | count={count}", count=len(edges))
        return edges

    def load_graph(self) -> Optional[nx.DiGraph]:
        """
        Load the full NetworkX DiGraph from graph.json.

        Returns:
            Restored NetworkX DiGraph, or None if file does not exist.
        """
        if not self._graph_path.exists():
            graph_log.warning("graph.json not found — graph not yet built")
            return None

        raw = self._read_json(self._graph_path)
        graph = nx.node_link_graph(raw, directed=True, multigraph=False)
        graph_log.info(
            "Loaded graph | nodes={n} | edges={e}",
            n=graph.number_of_nodes(),
            e=graph.number_of_edges(),
        )
        return graph

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def graph_exists(self) -> bool:
        """Return True if all three graph JSON files exist on disk."""
        return (
            self._nodes_path.exists()
            and self._edges_path.exists()
            and self._graph_path.exists()
        )

    def get_storage_paths(self) -> Dict[str, str]:
        """Return all storage file paths as a dictionary."""
        return {
            "nodes": str(self._nodes_path),
            "edges": str(self._edges_path),
            "graph": str(self._graph_path),
        }

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _atomic_write(self, path: Path, data: object) -> None:
        """
        Write JSON data atomically using a temporary file and rename.

        Prevents corrupt files if the process crashes mid-write.

        Args:
            path: Target file path.
            data: JSON-serializable object to write.
        """
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            os.replace(tmp_path, path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    def _read_json(self, path: Path) -> list:
        """
        Read and parse a JSON file, returning a list.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed JSON content as a list.
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
