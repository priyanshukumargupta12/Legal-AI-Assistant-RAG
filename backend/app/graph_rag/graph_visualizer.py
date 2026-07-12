"""
app/graph_rag/graph_visualizer.py
====================================
Interactive graph visualization generator for the Graph RAG module.

PURPOSE:
    Converts the NetworkX DiGraph into a D3.js-compatible JSON format
    that the frontend can directly render as an interactive force-directed
    graph without any additional transformation.

    Output format is compatible with:
        - D3-force (d3.forceSimulation)
        - vis.js Network
        - Sigma.js
        - Cytoscape.js

NODE VISUAL ENCODING:
    - Node size   → proportional to page_count (document size)
    - Node color  → determined by NodeType (Acts=blue, Judgments=red, Tax=green, etc.)
    - Node label  → document_name (filename without extension)

EDGE VISUAL ENCODING:
    - Edge width  → proportional to edge weight
    - Edge color  → determined by EdgeType
    - Edge label  → EdgeType.value (shown on hover)
    - Arrow type  → directed (source → target)

DESIGN:
    - Pure transformation: DiGraph → dict. No I/O, no state.
    - Color palette uses accessible, WCAG-compliant color codes.
    - Node groups map NodeType to integer for D3 categorical coloring.

SOLID: Single Responsibility — visualization serialization only.
"""

from __future__ import annotations

from typing import Any, Dict, List

import networkx as nx

from app.graph_rag.graph_logger import graph_log
from app.graph_rag.graph_models import EdgeType, GraphNode, NodeType


# =============================================================================
# VISUAL ENCODING MAPS
# =============================================================================

# Node colors by NodeType (D3-friendly hex codes)
_NODE_COLORS: Dict[str, str] = {
    NodeType.ACT.value:           "#4A90D9",   # Steel Blue — authority documents
    NodeType.COURT_JUDGMENT.value: "#E74C3C",  # Crimson Red — court decisions
    NodeType.TAX_DOCUMENT.value:  "#27AE60",   # Emerald Green — IRS publications
    NodeType.LEGAL_OPINION.value: "#9B59B6",   # Purple — attorney opinions
    NodeType.COMMENTARY.value:    "#F39C12",   # Amber — commentary & analysis
    NodeType.UNKNOWN.value:       "#95A5A6",   # Gray — unclassified
}

# Edge colors by EdgeType
_EDGE_COLORS: Dict[str, str] = {
    EdgeType.CITES.value:               "#E74C3C",   # Red — citation link
    EdgeType.REFERS_TO.value:           "#3498DB",   # Blue — reference link
    EdgeType.DISCUSSES.value:           "#9B59B6",   # Purple — discussion link
    EdgeType.EXPLAINS.value:            "#27AE60",   # Green — explanation link
    EdgeType.REFERENCES_SECTION.value:  "#F39C12",   # Amber — section reference
    EdgeType.OVERRULES.value:           "#E67E22",   # Orange — overruling
    EdgeType.AMENDS.value:              "#1ABC9C",   # Teal — amendment link
}

# Node group integer (used for D3 categorical color scales)
_NODE_GROUPS: Dict[str, int] = {
    NodeType.ACT.value:            1,
    NodeType.COURT_JUDGMENT.value: 2,
    NodeType.TAX_DOCUMENT.value:   3,
    NodeType.LEGAL_OPINION.value:  4,
    NodeType.COMMENTARY.value:     5,
    NodeType.UNKNOWN.value:        6,
}

# Base node radius (scaled by page_count)
_BASE_NODE_RADIUS: int = 12
_MAX_NODE_RADIUS: int = 40


class GraphVisualizer:
    """
    Converts the knowledge graph into a D3.js-compatible visualization format.

    Usage:
        visualizer = GraphVisualizer()
        viz_json = visualizer.to_d3(graph, node_map)
    """

    def to_d3(
        self,
        graph: nx.DiGraph,
        node_map: Dict[str, GraphNode],
    ) -> Dict[str, Any]:
        """
        Generate a D3.js-compatible graph visualization payload.

        OUTPUT STRUCTURE:
        {
            "nodes": [
                {
                    "id":    "<node_id>",
                    "label": "<document_name_without_extension>",
                    "type":  "<NodeType>",
                    "category": "<category>",
                    "color": "<hex_color>",
                    "group": <int>,
                    "size":  <int>,
                    "page_count": <int>,
                    "summary": "<summary_text>"
                }, ...
            ],
            "links": [
                {
                    "source": "<source_node_id>",
                    "target": "<target_node_id>",
                    "label":  "<EdgeType>",
                    "color":  "<hex_color>",
                    "width":  <float>,
                    "weight": <float>
                }, ...
            ],
            "metadata": {
                "total_nodes": <int>,
                "total_edges": <int>,
                "node_types":  { type: count, ... },
                "edge_types":  { type: count, ... }
            }
        }

        Args:
            graph:    NetworkX DiGraph (must be pre-built).
            node_map: Mapping from node_id → GraphNode.

        Returns:
            D3-compatible dict ready for JSON serialization.
        """
        graph_log.info(
            "Generating D3 visualization | nodes={n} | edges={e}",
            n=graph.number_of_nodes(),
            e=graph.number_of_edges(),
        )

        # ── Compute max page count for normalization ───────────────────────────
        max_pages = max(
            (n.page_count for n in node_map.values() if n.page_count > 0),
            default=1,
        )

        # ── Build node list ────────────────────────────────────────────────────
        d3_nodes: List[Dict[str, Any]] = []
        node_type_counts: Dict[str, int] = {}

        for node_id, node in node_map.items():
            # Skip nodes not in the graph
            if node_id not in graph:
                continue

            node_type_val = node.node_type.value
            node_type_counts[node_type_val] = node_type_counts.get(node_type_val, 0) + 1

            # Scale node size proportionally to page count
            size = _BASE_NODE_RADIUS
            if node.page_count > 0 and max_pages > 0:
                ratio = node.page_count / max_pages
                size = int(_BASE_NODE_RADIUS + ratio * (_MAX_NODE_RADIUS - _BASE_NODE_RADIUS))

            # Strip extension for cleaner label
            label = node.document_name.replace(".pdf", "").replace("_", " ")

            d3_nodes.append({
                "id":         node_id,
                "label":      label,
                "type":       node_type_val,
                "category":   node.category,
                "color":      _NODE_COLORS.get(node_type_val, "#95A5A6"),
                "group":      _NODE_GROUPS.get(node_type_val, 6),
                "size":       size,
                "page_count": node.page_count,
                "chunk_count": len(node.chunk_ids),
                "summary":    node.summary[:150] + "…" if len(node.summary) > 150 else node.summary,
            })

        # ── Build link list ────────────────────────────────────────────────────
        d3_links: List[Dict[str, Any]] = []
        edge_type_counts: Dict[str, int] = {}

        for src, tgt, data in graph.edges(data=True):
            edge_type_val = data.get("edge_type", "REFERS_TO")
            edge_type_counts[edge_type_val] = edge_type_counts.get(edge_type_val, 0) + 1

            weight = float(data.get("weight", 1.0))
            # Scale edge width: 1px base + up to 4px based on weight
            edge_width = round(1.0 + weight * 4.0, 2)

            d3_links.append({
                "source":           src,
                "target":           tgt,
                "label":            edge_type_val,
                "color":            _EDGE_COLORS.get(edge_type_val, "#BDC3C7"),
                "width":            edge_width,
                "weight":           weight,
                "confidence":       float(data.get("confidence", 1.0)),
                "detected_pattern": data.get("detected_pattern", ""),
                "occurrence_count": int(data.get("occurrence_count", 1)),
            })

        # ── Build metadata ─────────────────────────────────────────────────────
        metadata = {
            "total_nodes": len(d3_nodes),
            "total_edges": len(d3_links),
            "node_types":  node_type_counts,
            "edge_types":  edge_type_counts,
            "color_legend": {
                "nodes": {
                    k: _NODE_COLORS[k]
                    for k in _NODE_COLORS
                },
                "edges": {
                    k: _EDGE_COLORS[k]
                    for k in _EDGE_COLORS
                },
            },
        }

        graph_log.info(
            "D3 visualization generated | nodes={n} | links={l}",
            n=len(d3_nodes),
            l=len(d3_links),
        )

        return {
            "nodes":    d3_nodes,
            "links":    d3_links,
            "metadata": metadata,
        }
