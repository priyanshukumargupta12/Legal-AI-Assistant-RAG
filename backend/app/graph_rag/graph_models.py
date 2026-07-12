"""
app/graph_rag/graph_models.py
==============================
Pure Python dataclasses for the Graph RAG subsystem.

PURPOSE:
    Domain models representing graph nodes, edges, traversal results, and
    build statistics. Zero framework dependencies — only stdlib dataclasses
    and enums. Framework-agnostic and fully testable in isolation.

DESIGN:
    - NodeType enum maps document categories to graph node types.
    - EdgeType enum defines all legal relationship types supported.
    - GraphNode is the primary vertex of the knowledge graph.
    - GraphEdge is a directed, typed, weighted relationship.
    - GraphBuildResult captures post-build statistics.
    - GraphQueryResult captures graph traversal output for a single query.

WHY GRAPH RAG FOR LEGAL DOCUMENTS:
    Legal reasoning is inherently relational. A Court Judgment cites multiple
    Acts and IRS Publications. A Legal Opinion explains a statute and refers
    to prior judgments. These explicit cross-document reference chains are
    completely invisible to pure vector similarity search.

    Graph RAG makes these chains discoverable:
        Court Judgment → [CITES] → Act → [EXPLAINS] → IRS Publication
    Traversing two hops surfaces documents that are *legally relevant* even
    when they share almost no vocabulary with the user query.

SOLID: Each dataclass has exactly one responsibility.
DRY:   Node/edge types centralized here; never duplicated in service code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# ENUMERATIONS
# =============================================================================

class NodeType(str, Enum):
    """
    Enumeration of all legal document node types in the knowledge graph.

    Maps to the project's VALID_CATEGORIES plus additional document archetypes.
    Using str mixin allows NodeType values to be used directly in JSON output.
    """
    ACT = "ACT"                        # Statutory acts (e.g., ERISA, ADA)
    COURT_JUDGMENT = "COURT_JUDGMENT"  # Court decisions and case law
    TAX_DOCUMENT = "TAX_DOCUMENT"      # IRS Publications, tax guides
    LEGAL_OPINION = "LEGAL_OPINION"    # Attorney/OLC opinions
    COMMENTARY = "COMMENTARY"          # Legal commentary and analysis
    UNKNOWN = "UNKNOWN"                # Fallback for unclassified documents


class EdgeType(str, Enum):
    """
    Enumeration of directed relationship types between legal document nodes.

    Each edge type encodes a specific legal relationship:
        CITES              — Document A formally cites Document B (case law)
        REFERS_TO          — Document A refers to Document B by name/section
        DISCUSSES          — Document A discusses topics covered by Document B
        EXPLAINS           — Document A provides explanation of Document B's content
        REFERENCES_SECTION — Document A references a specific section of Document B
        OVERRULES          — Court Judgment A overrules prior Judgment B
        AMENDS             — Act A amends Act B
    """
    CITES = "CITES"
    REFERS_TO = "REFERS_TO"
    DISCUSSES = "DISCUSSES"
    EXPLAINS = "EXPLAINS"
    REFERENCES_SECTION = "REFERENCES_SECTION"
    OVERRULES = "OVERRULES"
    AMENDS = "AMENDS"


# =============================================================================
# GRAPH NODE
# =============================================================================

@dataclass
class GraphNode:
    """
    A vertex in the legal knowledge graph representing a single document.

    Attributes:
        node_id:       Unique identifier — derived from document_id or filename SHA256.
        node_type:     Legal classification of this document (NodeType enum).
        document_name: Source PDF filename (e.g., "IRS_Publication_550.pdf").
        category:      Raw category string from the dataset folder structure.
        page_count:    Total pages in the source document.
        summary:       Short auto-generated description (first 200 chars of content).
        chunk_ids:     List of all chunk IDs belonging to this document.
        metadata:      Pass-through dict for additional document attributes.
        created_at:    UTC timestamp when this node was added to the graph.
    """

    node_id: str
    node_type: NodeType
    document_name: str
    category: str
    page_count: int = 0
    summary: str = ""
    chunk_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        """Serialize GraphNode to a JSON-serializable dictionary."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "document_name": self.document_name,
            "category": self.category,
            "page_count": self.page_count,
            "summary": self.summary,
            "chunk_ids": self.chunk_ids,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GraphNode":
        """Deserialize a GraphNode from a JSON dictionary."""
        return cls(
            node_id=data["node_id"],
            node_type=NodeType(data.get("node_type", "UNKNOWN")),
            document_name=data["document_name"],
            category=data.get("category", ""),
            page_count=data.get("page_count", 0),
            summary=data.get("summary", ""),
            chunk_ids=data.get("chunk_ids", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(timezone.utc),
        )


# =============================================================================
# GRAPH EDGE
# =============================================================================

@dataclass
class GraphEdge:
    """
    A directed, typed, weighted relationship between two GraphNodes.

    Attributes:
        edge_id:           Unique ID — composed as "{source_id}→{target_id}→{edge_type}".
        source_id:         Node ID of the referencing document (origin of the relationship).
        target_id:         Node ID of the referenced document (destination).
        edge_type:         Semantic type of the relationship (EdgeType enum).
        weight:            Normalized confidence score 0.0–1.0. Higher = stronger relationship.
        confidence:        Raw match confidence from pattern detection (before normalization).
        detected_pattern:  The exact text fragment that triggered this edge (for traceability).
        occurrence_count:  Number of times this relationship was detected in the source text.
        created_at:        UTC timestamp of edge creation.
    """

    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    confidence: float = 1.0
    detected_pattern: str = ""
    occurrence_count: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        """Serialize GraphEdge to a JSON-serializable dictionary."""
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": round(self.weight, 4),
            "confidence": round(self.confidence, 4),
            "detected_pattern": self.detected_pattern,
            "occurrence_count": self.occurrence_count,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GraphEdge":
        """Deserialize a GraphEdge from a JSON dictionary."""
        return cls(
            edge_id=data["edge_id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            edge_type=EdgeType(data.get("edge_type", "REFERS_TO")),
            weight=float(data.get("weight", 1.0)),
            confidence=float(data.get("confidence", 1.0)),
            detected_pattern=data.get("detected_pattern", ""),
            occurrence_count=int(data.get("occurrence_count", 1)),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(timezone.utc),
        )


# =============================================================================
# GRAPH BUILD RESULT
# =============================================================================

@dataclass
class GraphBuildResult:
    """
    Output produced by a full graph build operation.

    Attributes:
        total_nodes:          Number of document nodes created.
        total_edges:          Number of directed edges detected.
        nodes_by_type:        Breakdown of nodes per NodeType.
        edges_by_type:        Breakdown of edges per EdgeType.
        build_time_ms:        Wall-clock time for the build operation.
        chunks_scanned:       Total chunk files scanned for patterns.
        patterns_matched:     Total regex pattern matches found.
        built_at:             UTC timestamp.
    """

    total_nodes: int = 0
    total_edges: int = 0
    nodes_by_type: Dict[str, int] = field(default_factory=dict)
    edges_by_type: Dict[str, int] = field(default_factory=dict)
    build_time_ms: float = 0.0
    chunks_scanned: int = 0
    patterns_matched: int = 0
    built_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# GRAPH QUERY RESULT
# =============================================================================

@dataclass
class GraphQueryResult:
    """
    Result of a graph traversal query.

    Attributes:
        query_node_ids:   Source node IDs used as traversal start points.
        expanded_nodes:   Neighbor nodes discovered via BFS traversal.
        edges_traversed:  Edges used during traversal (for explanation).
        depth:            BFS depth used in this traversal.
        traversal_time_ms: Wall-clock time for the traversal in ms.
        queried_at:       UTC timestamp.
    """

    query_node_ids: List[str]
    expanded_nodes: List[GraphNode] = field(default_factory=list)
    edges_traversed: List[GraphEdge] = field(default_factory=list)
    depth: int = 1
    traversal_time_ms: float = 0.0
    queried_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# GRAPH STATISTICS
# =============================================================================

@dataclass
class GraphStats:
    """
    Lightweight statistics about the current graph state.

    Attributes:
        total_nodes:    Number of document nodes.
        total_edges:    Number of directed relationship edges.
        node_types:     Count per NodeType.
        edge_types:     Count per EdgeType.
        density:        Graph density metric (edges / max_possible_edges).
        is_built:       Whether the graph has been constructed.
        last_built_at:  UTC timestamp of last build (None if never built).
    """

    total_nodes: int = 0
    total_edges: int = 0
    node_types: Dict[str, int] = field(default_factory=dict)
    edge_types: Dict[str, int] = field(default_factory=dict)
    density: float = 0.0
    is_built: bool = False
    last_built_at: Optional[datetime] = None
