"""
app/graph_rag/graph_utils.py
==============================
Stateless utility functions for the Graph RAG subsystem.

PURPOSE:
    Pure helper functions used by GraphBuilder, GraphSearch, and GraphService.
    No state, no side effects — all functions are deterministic given their inputs.

DESIGN:
    - Each function has a single, well-defined purpose.
    - Regex patterns are compiled at module load for performance.
    - Category-to-NodeType mapping centralizes classification logic.

SOLID: Single Responsibility — utility functions only.
DRY:   All shared helpers defined once; never duplicated.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.graph_rag.graph_models import EdgeType, NodeType


# =============================================================================
# CATEGORY → NODE TYPE MAPPING
# =============================================================================

_CATEGORY_NODE_TYPE_MAP: Dict[str, NodeType] = {
    "Acts": NodeType.ACT,
    "CourtJudgement": NodeType.COURT_JUDGMENT,
    "Tax": NodeType.TAX_DOCUMENT,
    "Legal_opinion": NodeType.LEGAL_OPINION,
    "Commentary": NodeType.COMMENTARY,
}


def category_to_node_type(category: str) -> NodeType:
    """
    Map a dataset category string to its corresponding NodeType enum.

    Args:
        category: Raw category folder name (e.g., "Acts", "Tax").

    Returns:
        Matching NodeType, or NodeType.UNKNOWN if not recognized.
    """
    return _CATEGORY_NODE_TYPE_MAP.get(category, NodeType.UNKNOWN)


# =============================================================================
# NODE ID GENERATION
# =============================================================================

def generate_node_id(document_name: str) -> str:
    """
    Generate a stable, deterministic node ID from a document filename.

    Uses SHA256 (first 12 hex chars) to produce a short, collision-resistant ID
    that is consistent across multiple graph builds.

    Args:
        document_name: PDF filename (e.g., "IRS_Publication_550.pdf").

    Returns:
        12-character hex string prefixed by category shortcode.

    Example:
        >>> generate_node_id("IRS_Publication_550.pdf")
        'node_3fa2b1c89d04'
    """
    digest = hashlib.sha256(document_name.encode("utf-8")).hexdigest()
    return f"node_{digest[:12]}"


def generate_edge_id(source_id: str, target_id: str, edge_type: EdgeType) -> str:
    """
    Generate a stable, unique edge identifier.

    Args:
        source_id:  Source node ID.
        target_id:  Target node ID.
        edge_type:  EdgeType enum value.

    Returns:
        Deterministic string of the form "src→tgt→EDGE_TYPE".
    """
    return f"{source_id}→{target_id}→{edge_type.value}"


# =============================================================================
# LEGAL REFERENCE DETECTION PATTERNS
# =============================================================================
# All patterns compiled once at module load for maximum performance.
# Each tuple: (compiled_pattern, edge_type, base_confidence)

_LEGAL_PATTERNS: List[Tuple[re.Pattern, EdgeType, float]] = [
    # Internal Revenue Code / U.S.C. section references
    (
        re.compile(
            r"(?:IRC|I\.R\.C\.|Internal\s+Revenue\s+Code)\s*§?\s*\d+[\w\-\.]*",
            re.IGNORECASE,
        ),
        EdgeType.REFERENCES_SECTION,
        0.90,
    ),
    # 26 U.S.C. references
    (
        re.compile(r"26\s+U\.S\.C\.\s*§?\s*\d+[\w\-\.]*", re.IGNORECASE),
        EdgeType.REFERENCES_SECTION,
        0.90,
    ),
    # CFR (Code of Federal Regulations) references
    (
        re.compile(r"\d+\s+C\.F\.R\.\s*(?:§\s*)?\d+[\w\-\.]*", re.IGNORECASE),
        EdgeType.REFERS_TO,
        0.85,
    ),
    # IRS Publication references  (e.g., "Pub. 550", "Publication 590-A")
    (
        re.compile(r"Pub(?:lication)?\.\s*\d+[\w\-]*", re.IGNORECASE),
        EdgeType.EXPLAINS,
        0.80,
    ),
    # Court case citation pattern  (e.g., "Smith v. Commissioner")
    (
        re.compile(
            r"[A-Z][a-zA-Z\s]+\s+v\.\s+[A-Z][a-zA-Z\s,]+(?:\d{4})?",
            re.MULTILINE,
        ),
        EdgeType.CITES,
        0.85,
    ),
    # Section reference  (e.g., "Section 162", "§ 409A")
    (
        re.compile(r"(?:Section|§)\s+\d+[\w\-\.]*", re.IGNORECASE),
        EdgeType.REFERENCES_SECTION,
        0.70,
    ),
    # Named Act reference  (e.g., "Employee Retirement Income Security Act")
    (
        re.compile(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Act\b"),
        EdgeType.REFERS_TO,
        0.75,
    ),
    # Court / Judgment keywords
    (
        re.compile(
            r"\b(?:Court|Judgment|Ruling|Decision|Opinion|Holding)\b",
            re.IGNORECASE,
        ),
        EdgeType.CITES,
        0.50,
    ),
    # "discusses" / "explains" language in legal opinions
    (
        re.compile(r"\b(?:discusses?|explains?|addresses?|analyzes?)\b", re.IGNORECASE),
        EdgeType.DISCUSSES,
        0.50,
    ),
    # "amends" language
    (
        re.compile(r"\bamends?\b", re.IGNORECASE),
        EdgeType.AMENDS,
        0.80,
    ),
    # "overrule" language
    (
        re.compile(r"\boverrul(?:es?|ing|ed)\b", re.IGNORECASE),
        EdgeType.OVERRULES,
        0.85,
    ),
]


def detect_legal_patterns(text: str) -> List[Tuple[str, EdgeType, float]]:
    """
    Scan a text fragment for legal reference patterns.

    Returns a list of (matched_text, edge_type, confidence) tuples for every
    distinct pattern match found in the text. Deduplicates matches by value.

    Args:
        text: Raw chunk text to scan.

    Returns:
        List of (matched_string, EdgeType, confidence_score) tuples.
        Ordered by confidence descending.
    """
    results: List[Tuple[str, EdgeType, float]] = []
    seen: Set[str] = set()

    for pattern, edge_type, confidence in _LEGAL_PATTERNS:
        for match in pattern.finditer(text):
            matched = match.group(0).strip()
            # Deduplicate by normalizing whitespace
            normalized_matched = re.sub(r'\s+', ' ', matched).lower()
            key = f"{edge_type.value}::{normalized_matched}"
            if key not in seen and len(matched) >= 3:
                seen.add(key)
                results.append((matched, edge_type, confidence))

    # Sort by confidence descending
    results.sort(key=lambda x: x[2], reverse=True)
    return results


# =============================================================================
# DOCUMENT NAME NORMALIZATION
# =============================================================================

def normalize_document_name(document_name: str) -> str:
    """
    Normalize a document filename for consistent comparison.

    Strips path separators, removes extension, lowercases.

    Args:
        document_name: Raw filename (e.g., "IRS_Publication_550.pdf").

    Returns:
        Normalized string (e.g., "irs_publication_550").
    """
    stem = Path(document_name).stem
    return stem.lower().replace(" ", "_").replace("-", "_")


def extract_document_summary(text: str, max_chars: int = 250) -> str:
    """
    Extract a short summary from the beginning of a document's text content.

    Removes excessive whitespace and truncates cleanly at a word boundary.

    Args:
        text:      Raw text (e.g., first chunk content).
        max_chars: Maximum summary length in characters.

    Returns:
        Cleaned, truncated summary string.
    """
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned

    # Truncate at last space before max_chars
    truncated = cleaned[:max_chars]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] + "…") if last_space > 0 else truncated + "…"


# =============================================================================
# GRAPH DENSITY
# =============================================================================

def compute_graph_density(node_count: int, edge_count: int) -> float:
    """
    Compute the density of a directed graph.

    Density = edges / (nodes * (nodes - 1)) for a directed graph.
    Returns 0.0 if node_count < 2.

    Args:
        node_count: Number of nodes in the graph.
        edge_count: Number of directed edges.

    Returns:
        Density as a float between 0.0 and 1.0.
    """
    if node_count < 2:
        return 0.0
    max_edges = node_count * (node_count - 1)
    return round(edge_count / max_edges, 6)
