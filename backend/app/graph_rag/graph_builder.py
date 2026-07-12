"""
app/graph_rag/graph_builder.py
================================
Knowledge graph construction engine for the Graph RAG module.

PURPOSE:
    Scans the metadata/chunks/ directory to discover all indexed documents,
    creates GraphNode objects for each unique document, detects cross-document
    legal reference relationships by scanning chunk text, and builds a
    NetworkX DiGraph populated with typed, weighted edges.

ALGORITHM:
    1. Load all chunk JSON files from metadata/chunks/
    2. Group chunks by document_name → build one GraphNode per document
    3. For each chunk's text, run legal pattern detection
    4. Resolve detected references to known document node IDs
    5. Create directed GraphEdge objects with weights and confidence scores
    6. Construct NetworkX DiGraph from nodes + edges
    7. Persist via GraphRepository

DESIGN:
    - GraphBuilder is stateless per build; re-instantiation is safe.
    - Pattern matching uses pre-compiled regex from graph_utils.
    - LangChain's text_splitter utilities normalize whitespace pre-scan.
    - Minimum confidence threshold filters low-quality edges.

SOLID:
    Single Responsibility — graph construction only.
    Open/Closed — new edge types added by extending _LEGAL_PATTERNS in utils.
    Dependency Inversion — depends on GraphRepository abstraction.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from app.graph_rag.graph_logger import graph_log
from app.graph_rag.graph_models import (
    EdgeType,
    GraphBuildResult,
    GraphEdge,
    GraphNode,
    NodeType,
)
from app.graph_rag.graph_repository import GraphRepository
from app.graph_rag.graph_utils import (
    category_to_node_type,
    compute_graph_density,
    detect_legal_patterns,
    extract_document_summary,
    generate_edge_id,
    generate_node_id,
    normalize_document_name,
)


class GraphBuilder:
    """
    Builds the legal knowledge graph from indexed chunk metadata files.

    Constructor Args:
        repository:          Injected GraphRepository for persistence.
        chunks_dir:          Directory containing chunk JSON files (metadata/chunks/).
        min_edge_confidence: Minimum confidence threshold for edges (default: 0.3).
    """

    def __init__(
        self,
        repository: GraphRepository,
        chunks_dir: Path,
        min_edge_confidence: float = 0.3,
    ) -> None:
        """
        Initialize the GraphBuilder.

        Args:
            repository:          GraphRepository for saving the built graph.
            chunks_dir:          Root directory containing chunk JSON files.
            min_edge_confidence: Edges with confidence below this are discarded.
        """
        self._repo = repository
        self._chunks_dir = chunks_dir
        self._min_confidence = min_edge_confidence

        graph_log.info(
            "GraphBuilder initialized | chunks_dir={dir} | min_confidence={conf}",
            dir=str(chunks_dir),
            conf=min_edge_confidence,
        )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def build(self) -> Tuple[List[GraphNode], List[GraphEdge], nx.DiGraph, GraphBuildResult]:
        """
        Execute the full graph construction pipeline.

        PIPELINE:
            1. Load all chunk files and group by document
            2. Create GraphNode for each unique document
            3. Scan chunk text for legal reference patterns
            4. Resolve references to known document nodes → create GraphEdge
            5. Build NetworkX DiGraph
            6. Persist via repository
            7. Return results + statistics

        Returns:
            Tuple of (nodes, edges, nx_graph, build_result).

        Raises:
            FileNotFoundError: If chunks_dir does not exist or is empty.
        """
        start_time = time.perf_counter()
        graph_log.info("Graph build started | chunks_dir={dir}", dir=str(self._chunks_dir))

        # ── Step 1: Load all chunk files ─────────────────────────────────────
        chunk_files = self._discover_chunk_files()
        graph_log.info("Chunk files discovered | count={count}", count=len(chunk_files))

        if not chunk_files:
            graph_log.warning("No chunk files found — graph will be empty")

        # ── Step 2: Group chunks by document and build nodes ──────────────────
        doc_chunks: Dict[str, List[dict]] = defaultdict(list)
        chunks_scanned = 0

        for chunk_file in chunk_files:
            try:
                chunks = self._load_chunk_file(chunk_file)
                for chunk in chunks:
                    doc_name = chunk.get("document_name", chunk.get("document", ""))
                    if doc_name:
                        doc_chunks[doc_name].append(chunk)
                        chunks_scanned += 1
            except Exception as exc:  # noqa: BLE001
                graph_log.error(
                    "Failed to load chunk file | file={f} | error={e}",
                    f=chunk_file.name,
                    e=str(exc),
                )

        graph_log.info(
            "Documents discovered | docs={docs} | chunks={chunks}",
            docs=len(doc_chunks),
            chunks=chunks_scanned,
        )

        # ── Step 3: Build GraphNode objects ───────────────────────────────────
        nodes: List[GraphNode] = []
        node_id_map: Dict[str, str] = {}           # document_name → node_id
        normalized_map: Dict[str, str] = {}         # normalized_name → node_id

        for doc_name, chunks in doc_chunks.items():
            node = self._create_node(doc_name, chunks)
            nodes.append(node)
            node_id_map[doc_name] = node.node_id
            normalized_map[normalize_document_name(doc_name)] = node.node_id

            graph_log.debug(
                "Node created | id={id} | type={type} | doc={doc}",
                id=node.node_id,
                type=node.node_type.value,
                doc=doc_name,
            )

        graph_log.info("GraphNodes created | count={count}", count=len(nodes))

        # ── Step 4: Detect relationships and create edges ────────────────────
        edges, patterns_matched = self._detect_edges(
            doc_chunks=doc_chunks,
            node_id_map=node_id_map,
            normalized_map=normalized_map,
        )

        graph_log.info(
            "Edges detected | count={count} | patterns_matched={pm}",
            count=len(edges),
            pm=patterns_matched,
        )

        # ── Step 5: Build NetworkX DiGraph ────────────────────────────────────
        nx_graph = self._build_nx_graph(nodes, edges)

        # ── Step 6: Persist ───────────────────────────────────────────────────
        self._repo.save_all(nodes, edges, nx_graph)

        # ── Step 7: Compile build result ──────────────────────────────────────
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        nodes_by_type: Dict[str, int] = defaultdict(int)
        for n in nodes:
            nodes_by_type[n.node_type.value] += 1

        edges_by_type: Dict[str, int] = defaultdict(int)
        for e in edges:
            edges_by_type[e.edge_type.value] += 1

        build_result = GraphBuildResult(
            total_nodes=len(nodes),
            total_edges=len(edges),
            nodes_by_type=dict(nodes_by_type),
            edges_by_type=dict(edges_by_type),
            build_time_ms=round(elapsed_ms, 2),
            chunks_scanned=chunks_scanned,
            patterns_matched=patterns_matched,
        )

        graph_log.info(
            "Graph build complete | nodes={n} | edges={e} | time={t:.1f}ms",
            n=len(nodes),
            e=len(edges),
            t=elapsed_ms,
        )

        return nodes, edges, nx_graph, build_result

    # =========================================================================
    # PRIVATE — FILE DISCOVERY
    # =========================================================================

    def _discover_chunk_files(self) -> List[Path]:
        """
        Recursively find all chunk JSON files in the chunks directory.

        Returns:
            List of Path objects pointing to chunk JSON files.
        """
        if not self._chunks_dir.exists():
            graph_log.warning(
                "Chunks directory does not exist | dir={dir}",
                dir=str(self._chunks_dir),
            )
            return []

        chunk_files = sorted(self._chunks_dir.rglob("*_chunks.json"))
        if not chunk_files:
            # Fallback: any .json file in the directory
            chunk_files = sorted(self._chunks_dir.rglob("*.json"))

        return chunk_files

    def _load_chunk_file(self, path: Path) -> List[dict]:
        """
        Load and parse a chunk JSON file.

        The file may contain a list of chunks directly, or a dict with a
        "chunks" key (depending on the ChunkingService output format).

        Args:
            path: Path to the chunk JSON file.

        Returns:
            List of chunk dictionaries.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("chunks", [])
        return []

    # =========================================================================
    # PRIVATE — NODE CREATION
    # =========================================================================

    def _create_node(self, doc_name: str, chunks: List[dict]) -> GraphNode:
        """
        Build a GraphNode from a document name and its associated chunks.

        Args:
            doc_name: PDF filename.
            chunks:   All chunk dicts belonging to this document.

        Returns:
            Populated GraphNode instance.
        """
        # Derive category from first chunk
        category = chunks[0].get("category", "Unknown") if chunks else "Unknown"
        node_type = category_to_node_type(category)

        # Derive page count from max page number seen
        page_numbers = [
            c.get("page_number", c.get("page", 0)) for c in chunks
        ]
        page_count = max(page_numbers) if page_numbers else 0

        # Build summary from first chunk's text
        first_text = chunks[0].get("text", chunks[0].get("chunk_text", "")) if chunks else ""
        summary = extract_document_summary(first_text, max_chars=250)

        # Collect chunk IDs
        chunk_ids = [
            c.get("chunk_id", c.get("id", "")) for c in chunks if c.get("chunk_id") or c.get("id")
        ]

        node_id = generate_node_id(doc_name)

        return GraphNode(
            node_id=node_id,
            node_type=node_type,
            document_name=doc_name,
            category=category,
            page_count=page_count,
            summary=summary,
            chunk_ids=chunk_ids,
            metadata={"source": "chunk_scan", "chunk_count": str(len(chunks))},
        )

    # =========================================================================
    # PRIVATE — EDGE DETECTION
    # =========================================================================

    def _detect_edges(
        self,
        doc_chunks: Dict[str, List[dict]],
        node_id_map: Dict[str, str],
        normalized_map: Dict[str, str],
    ) -> Tuple[List[GraphEdge], int]:
        """
        Scan all chunk texts and detect cross-document legal references.

        ALGORITHM:
            For each chunk of document A:
                1. Run detect_legal_patterns() → list of (match, edge_type, confidence)
                2. Try to resolve each match to a known document node B
                3. If A ≠ B and confidence ≥ threshold → create/update edge A→B

        Args:
            doc_chunks:     Map of document_name → chunk dicts.
            node_id_map:    Map of document_name → node_id.
            normalized_map: Map of normalized_name → node_id.

        Returns:
            Tuple of (edge_list, total_pattern_matches_count).
        """
        # edge_key → {edge_type, max_confidence, occurrence_count, best_pattern}
        edge_accumulator: Dict[str, dict] = {}
        total_patterns = 0

        for source_doc, chunks in doc_chunks.items():
            source_id = node_id_map[source_doc]

            for chunk in chunks:
                text = chunk.get("text", chunk.get("chunk_text", ""))
                if not text:
                    continue

                matches = detect_legal_patterns(text)
                total_patterns += len(matches)

                for matched_text, edge_type, confidence in matches:
                    if confidence < self._min_confidence:
                        continue

                    # Attempt to resolve matched text to a known target document
                    target_id = self._resolve_reference(
                        matched_text=matched_text,
                        source_id=source_id,
                        node_id_map=node_id_map,
                        normalized_map=normalized_map,
                    )

                    if target_id is None:
                        continue  # Could not resolve to known document

                    edge_key = generate_edge_id(source_id, target_id, edge_type)

                    if edge_key not in edge_accumulator:
                        edge_accumulator[edge_key] = {
                            "source_id": source_id,
                            "target_id": target_id,
                            "edge_type": edge_type,
                            "max_confidence": confidence,
                            "occurrence_count": 1,
                            "best_pattern": matched_text,
                        }
                    else:
                        acc = edge_accumulator[edge_key]
                        acc["occurrence_count"] += 1
                        if confidence > acc["max_confidence"]:
                            acc["max_confidence"] = confidence
                            acc["best_pattern"] = matched_text

        # Convert accumulator to GraphEdge objects
        edges: List[GraphEdge] = []
        for edge_key, acc in edge_accumulator.items():
            # Weight = confidence boosted by occurrence frequency (capped at 1.0)
            raw_confidence = acc["max_confidence"]
            occurrence_boost = min(0.1 * (acc["occurrence_count"] - 1), 0.2)
            weight = min(raw_confidence + occurrence_boost, 1.0)

            edges.append(
                GraphEdge(
                    edge_id=edge_key,
                    source_id=acc["source_id"],
                    target_id=acc["target_id"],
                    edge_type=acc["edge_type"],
                    weight=round(weight, 4),
                    confidence=round(raw_confidence, 4),
                    detected_pattern=acc["best_pattern"],
                    occurrence_count=acc["occurrence_count"],
                )
            )

            graph_log.debug(
                "Edge created | {src} →[{type}]→ {tgt} | conf={conf:.2f} | n={n}",
                src=acc["source_id"],
                type=acc["edge_type"].value,
                tgt=acc["target_id"],
                conf=raw_confidence,
                n=acc["occurrence_count"],
            )

        return edges, total_patterns

    def _resolve_reference(
        self,
        matched_text: str,
        source_id: str,
        node_id_map: Dict[str, str],
        normalized_map: Dict[str, str],
    ) -> Optional[str]:
        """
        Attempt to resolve a matched text fragment to a known document node ID.

        STRATEGY:
            1. Check if any known document name is a substring of the matched text.
            2. Check if the normalized match overlaps with any normalized document name.
            3. Return None if no match found (pattern references unknown document).

        Args:
            matched_text:   The raw matched string (e.g., "Pub. 550").
            source_id:      Source node ID (skip self-references).
            node_id_map:    document_name → node_id.
            normalized_map: normalized_name → node_id.

        Returns:
            Target node ID string, or None if unresolvable.
        """
        matched_lower = matched_text.lower()
        matched_normalized = normalize_document_name(matched_text)

        # Strategy 1: Check if any document name appears in the matched text
        for doc_name, node_id in node_id_map.items():
            if node_id == source_id:
                continue
            doc_stem = Path(doc_name).stem.lower()
            if doc_stem in matched_lower or matched_lower in doc_stem:
                return node_id

        # Strategy 2: Normalized overlap
        for norm_name, node_id in normalized_map.items():
            if node_id == source_id:
                continue
            # Check significant overlap (4+ chars)
            if (
                len(matched_normalized) >= 4
                and (
                    matched_normalized in norm_name
                    or norm_name in matched_normalized
                )
            ):
                return node_id

        return None

    # =========================================================================
    # PRIVATE — NETWORKX GRAPH CONSTRUCTION
    # =========================================================================

    def _build_nx_graph(
        self,
        nodes: List[GraphNode],
        edges: List[GraphEdge],
    ) -> nx.DiGraph:
        """
        Construct a NetworkX DiGraph from GraphNode and GraphEdge lists.

        Node attributes stored: node_type, document_name, category, page_count, summary.
        Edge attributes stored: edge_type, weight, confidence, detected_pattern.

        Args:
            nodes: All GraphNode instances.
            edges: All GraphEdge instances.

        Returns:
            Populated NetworkX DiGraph.
        """
        G = nx.DiGraph()

        # Add nodes
        for node in nodes:
            G.add_node(
                node.node_id,
                node_type=node.node_type.value,
                document_name=node.document_name,
                category=node.category,
                page_count=node.page_count,
                summary=node.summary,
            )

        # Add edges
        for edge in edges:
            G.add_edge(
                edge.source_id,
                edge.target_id,
                edge_id=edge.edge_id,
                edge_type=edge.edge_type.value,
                weight=edge.weight,
                confidence=edge.confidence,
                detected_pattern=edge.detected_pattern,
                occurrence_count=edge.occurrence_count,
            )

        graph_log.info(
            "NetworkX graph built | nodes={n} | edges={e} | density={d:.6f}",
            n=G.number_of_nodes(),
            e=G.number_of_edges(),
            d=compute_graph_density(G.number_of_nodes(), G.number_of_edges()),
        )

        return G
