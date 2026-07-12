"""
app/knowledge/knowledge_utils.py
====================================
Stateless NLP extraction utilities for the OKF Standardization Module.

PURPOSE:
    Pure functions with no side effects that extract structured knowledge signals
    from raw legal document text:
        - Named entity detection (regex + keyword lookup)
        - Keyword extraction (frequency-based, stopword-filtered)
        - Legal section reference detection
        - Cross-document reference detection
        - Knowledge relation annotation

    All extraction is rule-based and uses only Python stdlib (re, collections).
    Zero external NLP dependencies (no spaCy, no NLTK, no transformers).

WHY RULE-BASED EXTRACTION (NO ML):
    1. Reproducible — deterministic output for the same input.
    2. Fast — no model loading or GPU inference; runs on CPU in microseconds.
    3. Consistent — same patterns used across OKF build, Graph RAG build,
       and evaluation, preventing divergent results.
    4. Maintainable — patterns are readable, auditable regex strings.
    5. Zero dependencies — no new packages required.

DESIGN:
    - All regex patterns are compiled at module load for performance.
    - LEGAL_STOPWORDS is a curated domain-specific list; supplements English stopwords.
    - Every function is pure (input → output; no state).
    - Deduplication is applied in all extraction functions.

SOLID: Single Responsibility — extraction utilities only.
DRY:   All patterns defined once here; never duplicated in builder or controller.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Set, Tuple

from app.knowledge.knowledge_models import EntityType, KnowledgeRelation, NamedEntity


# =============================================================================
# LEGAL STOPWORDS
# =============================================================================
# Extended English stopwords for the legal domain.
# Removes common structural and connector words that add no retrieval signal.

LEGAL_STOPWORDS: Set[str] = {
    # English general
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "each", "more", "also",
    "then", "than", "so", "if", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "no", "nor", "yet", "both", "either", "neither", "one", "two", "three",
    "any", "all", "most", "other", "such", "same", "own", "under", "over",
    "it", "its", "this", "that", "these", "those", "he", "she", "they",
    "we", "you", "i", "me", "him", "her", "us", "them", "their", "our",
    "your", "my", "his", "its", "who", "which", "what", "when", "where",
    "how", "why",
    # Legal structural words (low signal)
    "see", "per", "pursuant", "herein", "thereof", "therein", "thereto",
    "hereof", "hereby", "herewith", "whereas", "hereafter", "therefore",
    "accordingly", "provided", "however", "provided", "notwithstanding",
    "including", "without", "within", "upon", "unless", "until", "further",
    "following", "applies", "apply", "applicable", "accordance", "respect",
    "regard", "whether", "made", "make", "makes", "taken", "take", "takes",
    "given", "give", "gives", "set", "sets", "use", "used", "using",
    "based", "defined", "determined", "considered", "required", "provides",
    "generally", "specific", "certain", "particular", "general", "following",
    "related", "regarding", "mean", "means", "include", "includes",
    # Numbers and short tokens handled by minimum length filter
}


# =============================================================================
# ENTITY DETECTION PATTERNS
# =============================================================================
# Each tuple: (compiled_pattern, EntityType, confidence_score)
# Ordered from most specific (highest confidence) to least specific.

_ENTITY_PATTERNS: List[Tuple[re.Pattern, EntityType, float]] = [
    # IRC — Internal Revenue Code (highest legal specificity)
    (re.compile(r"I\.?R\.?C\.?\s*§?\s*\d+[\w\-\.]*", re.IGNORECASE), EntityType.LAW, 0.95),
    # 26 U.S.C. references
    (re.compile(r"26\s+U\.S\.C\.?\s*§?\s*\d+[\w\-\.]*", re.IGNORECASE), EntityType.LAW, 0.93),
    # CFR references
    (re.compile(r"\d+\s+C\.?F\.?R\.?\s*(?:§\s*)?\d+[\w\-\.]*", re.IGNORECASE), EntityType.CFR, 0.90),
    # IRS Publications
    (re.compile(r"Pub(?:lication)?\.\s*\d+[\w\-]*", re.IGNORECASE), EntityType.PUBLICATION, 0.90),
    # IRS / Revenue organizations
    (re.compile(r"\b(?:IRS|Internal\s+Revenue\s+Service)\b", re.IGNORECASE), EntityType.ORG, 0.95),
    (re.compile(r"\b(?:SEC|Securities\s+and\s+Exchange\s+Commission)\b", re.IGNORECASE), EntityType.ORG, 0.95),
    (re.compile(r"\b(?:DOJ|Department\s+of\s+Justice)\b", re.IGNORECASE), EntityType.ORG, 0.90),
    (re.compile(r"\bDepartment\s+of\s+[A-Z][a-z]+\b"), EntityType.ORG, 0.80),
    (re.compile(r"\bBureau\s+of\s+[A-Z][a-z]+\b"), EntityType.ORG, 0.80),
    # Court references
    (re.compile(
        r"\b(?:Tax\s+Court|United\s+States\s+Tax\s+Court|Circuit\s+Court|"
        r"District\s+Court|Court\s+of\s+Appeals|Supreme\s+Court|"
        r"U\.S\.C\.A\.|U\.S\.D\.C\.)\b", re.IGNORECASE),
        EntityType.COURT, 0.90,
    ),
    # Named Acts
    (re.compile(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Act\b"), EntityType.ACT, 0.85),
    # Section references
    (re.compile(r"(?:Section|§)\s+\d+[\w\-\.]*(?:\([a-z]\))?", re.IGNORECASE), EntityType.SECTION, 0.80),
    # Dollar amounts
    (re.compile(r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|thousand))?", re.IGNORECASE), EntityType.MONEY, 0.85),
    # Legal dates (Month Day, Year format)
    (re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b"
    ), EntityType.DATE, 0.85),
    # Person names (heuristic: Title + Capitalized Last Name, or two capitalized words)
    (re.compile(r"\b(?:Mr\.|Ms\.|Mrs\.|Dr\.|Judge|Commissioner|Petitioner|Respondent)\s+[A-Z][a-z]+\b"), EntityType.PERSON, 0.75),
]


# =============================================================================
# LEGAL SECTION DETECTION PATTERNS
# =============================================================================

_SECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"I\.?R\.?C\.?\s*§?\s*\d+[\w\-\.]*(?:\([a-z0-9]+\))*", re.IGNORECASE),
    re.compile(r"26\s+U\.S\.C\.?\s*§?\s*\d+[\w\-\.]*", re.IGNORECASE),
    re.compile(r"\d+\s+C\.?F\.?R\.?\s*(?:§\s*)?\d+[\w\-\.]*", re.IGNORECASE),
    re.compile(r"(?:Section|§)\s+\d+[\w\-\.]*(?:\([a-z0-9]+\))?", re.IGNORECASE),
    re.compile(r"Treas(?:ury)?\.\s*Reg(?:ulation)?\.?\s*§?\s*[\d\.]+[\w\-\.]*", re.IGNORECASE),
    re.compile(r"Rev(?:enue)?\.\s*(?:Rul(?:ing)?|Proc(?:edure)?)\.\s*\d+[-–]\d+", re.IGNORECASE),
]


# =============================================================================
# REFERENCE DETECTION PATTERNS (cross-document)
# =============================================================================
# These patterns detect text that references other documents.
# Returns (matched_text, relation_type, confidence) tuples.

_REFERENCE_PATTERNS: List[Tuple[re.Pattern, str, float]] = [
    (re.compile(r"Pub(?:lication)?\.\s*\d+[\w\-]*", re.IGNORECASE), "EXPLAINS", 0.88),
    (re.compile(r"[A-Z][a-zA-Z\s]+\s+v\.\s+[A-Z][a-zA-Z\s,]+(?:\d{4})?", re.MULTILINE), "CITES", 0.85),
    (re.compile(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Act\b"), "REFERS_TO", 0.80),
    (re.compile(r"I\.?R\.?C\.?\s*§?\s*\d+[\w\-\.]*", re.IGNORECASE), "REFERENCES_SECTION", 0.90),
    (re.compile(r"26\s+U\.S\.C\.?\s*§?\s*\d+[\w\-\.]*", re.IGNORECASE), "REFERENCES_SECTION", 0.90),
    (re.compile(r"\d+\s+C\.?F\.?R\.?\s*(?:§\s*)?\d+[\w\-\.]*", re.IGNORECASE), "REFERS_TO", 0.85),
    (re.compile(r"\b(?:discusses?|explains?|addresses?|analyzes?)\b", re.IGNORECASE), "DISCUSSES", 0.50),
    (re.compile(r"\bamends?\b", re.IGNORECASE), "AMENDS", 0.80),
    (re.compile(r"\boverrul(?:es?|ing|ed)\b", re.IGNORECASE), "OVERRULES", 0.85),
]


# =============================================================================
# ENTITY EXTRACTION
# =============================================================================

def extract_entities(text: str, max_entities: int = 30) -> List[NamedEntity]:
    """
    Extract named entities from legal text using compiled regex patterns.

    Applies all entity patterns in priority order (most specific first).
    Deduplicates by normalized text+type key. Caps results at max_entities.

    Args:
        text:         Raw chunk text.
        max_entities: Maximum number of unique entities to return.

    Returns:
        List of NamedEntity objects, ordered by confidence descending.
    """
    results: List[NamedEntity] = []
    seen: Set[str] = set()

    for pattern, entity_type, confidence in _ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            matched = match.group(0).strip()
            # Skip very short matches (likely false positives)
            if len(matched) < 2:
                continue
            # Normalize key for deduplication
            key = f"{entity_type.value}::{matched.lower().strip()}"
            if key not in seen:
                seen.add(key)
                results.append(NamedEntity(
                    text=matched,
                    entity_type=entity_type,
                    confidence=confidence,
                ))

    # Sort by confidence descending, then truncate
    results.sort(key=lambda e: e.confidence, reverse=True)
    return results[:max_entities]


# =============================================================================
# KEYWORD EXTRACTION
# =============================================================================

def extract_keywords(text: str, top_n: int = 15, min_length: int = 4) -> List[str]:
    """
    Extract top-N high-signal keywords from legal text via frequency analysis.

    ALGORITHM:
        1. Lowercase and tokenize on word boundaries.
        2. Filter: keep tokens with length >= min_length.
        3. Filter: remove tokens in LEGAL_STOPWORDS.
        4. Count remaining token frequencies.
        5. Return top-N tokens by frequency, alphabetically sorted on ties.

    This approach produces domain-relevant keywords without any ML model.
    Legal documents have highly repetitive terminology, making frequency-based
    extraction effective for domain-specific terms.

    Args:
        text:       Raw chunk text.
        top_n:      Number of keywords to return.
        min_length: Minimum token length to consider.

    Returns:
        List of keyword strings (top_n most frequent, stopwords removed).
    """
    # Tokenize
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z\-']*\b", text)

    # Normalize, filter stopwords and short tokens
    filtered = [
        t.lower()
        for t in tokens
        if len(t) >= min_length and t.lower() not in LEGAL_STOPWORDS
    ]

    if not filtered:
        return []

    # Count frequencies
    counter = Counter(filtered)

    # Return top-N sorted by count (then alpha for tie-breaking)
    top_items = counter.most_common(top_n)
    # Sort: primary = count desc, secondary = alpha asc
    top_items.sort(key=lambda x: (-x[1], x[0]))
    return [word for word, _ in top_items]


# =============================================================================
# LEGAL SECTION DETECTION
# =============================================================================

def extract_legal_sections(text: str) -> List[str]:
    """
    Extract all legal section references from text.

    Detects:
        - IRC / I.R.C. section references (§ 162, § 409A)
        - 26 U.S.C. references
        - CFR / C.F.R. references
        - Section / § generic references
        - Treasury Regulation references
        - Revenue Ruling / Revenue Procedure references

    Args:
        text: Raw chunk text.

    Returns:
        Deduplicated list of matched section reference strings.
    """
    results: List[str] = []
    seen: Set[str] = set()

    for pattern in _SECTION_PATTERNS:
        for match in pattern.finditer(text):
            matched = match.group(0).strip()
            normalized = re.sub(r"\s+", " ", matched).lower()
            if len(normalized) >= 3 and normalized not in seen:
                seen.add(normalized)
                results.append(matched)

    return results


# =============================================================================
# REFERENCE DETECTION
# =============================================================================

def extract_references(text: str) -> List[str]:
    """
    Extract cross-document reference strings from text.

    Detects references to other legal documents:
        - IRS Publications (Pub. 550)
        - Court cases (Smith v. Commissioner)
        - Named Acts (Employee Retirement Income Security Act)
        - IRC/CFR sections (used as document cross-references)
        - Explanatory/amendment language

    Args:
        text: Raw chunk text.

    Returns:
        Deduplicated list of matched reference strings.
    """
    results: List[str] = []
    seen: Set[str] = set()

    for pattern, _, _ in _REFERENCE_PATTERNS:
        for match in pattern.finditer(text):
            matched = match.group(0).strip()
            normalized = re.sub(r"\s+", " ", matched).lower()
            if len(normalized) >= 3 and normalized not in seen:
                seen.add(normalized)
                results.append(matched)

    return results


# =============================================================================
# KNOWLEDGE RELATION DETECTION
# =============================================================================

def extract_relations(text: str, min_confidence: float = 0.4) -> List[KnowledgeRelation]:
    """
    Extract typed KnowledgeRelation objects from text.

    These annotations make each chunk "Graph RAG ready":
        - CITES → this chunk references a court case
        - REFERS_TO → this chunk references an Act, CFR, or document
        - DISCUSSES → explanatory language detected
        - EXPLAINS → IRS publication reference
        - REFERENCES_SECTION → specific legal section reference
        - AMENDS / OVERRULES → legislative/judicial modification language

    Args:
        text:           Raw chunk text.
        min_confidence: Minimum confidence threshold for inclusion.

    Returns:
        List of KnowledgeRelation objects with unique target_ref strings.
    """
    results: List[KnowledgeRelation] = []
    seen: Set[str] = set()

    for pattern, relation_type, confidence in _REFERENCE_PATTERNS:
        if confidence < min_confidence:
            continue

        for match in pattern.finditer(text):
            matched = match.group(0).strip()
            key = f"{relation_type}::{matched.lower()}"
            if key not in seen and len(matched) >= 3:
                seen.add(key)
                results.append(KnowledgeRelation(
                    relation_type=relation_type,
                    target_ref=matched,
                    confidence=confidence,
                ))

    # Sort by confidence descending
    results.sort(key=lambda r: r.confidence, reverse=True)
    return results


# =============================================================================
# ID GENERATORS
# =============================================================================

def generate_knowledge_id(chunk_id: str) -> str:
    """
    Generate the OKF knowledge_id for a chunk.

    Format: "okf_{chunk_id}"
    Example: "okf_00b599d7_PAGE001_CHUNK000"

    Args:
        chunk_id: Source chunk ID from the Chunking Module.

    Returns:
        Deterministic knowledge_id string.
    """
    return f"okf_{chunk_id}"


def generate_document_knowledge_id(document_id: str) -> str:
    """
    Generate the OKF knowledge_id for a document.

    Format: "okf_doc_{document_id_prefix}"
    Example: "okf_doc_00b599d7"

    Args:
        document_id: UUID of the source document.

    Returns:
        Deterministic document-level knowledge_id string.
    """
    # Use first 8 chars of the UUID (same prefix as chunk_id convention)
    prefix = document_id.replace("-", "")[:8]
    return f"okf_doc_{prefix}"


# =============================================================================
# AGGREGATE HELPERS
# =============================================================================

def deduplicate_entities(entities: List[NamedEntity]) -> List[NamedEntity]:
    """
    Deduplicate a list of NamedEntity objects by (text, entity_type) key.

    Keeps the instance with the highest confidence score for each unique entity.

    Args:
        entities: List of NamedEntity objects (possibly from multiple chunks).

    Returns:
        Deduplicated list of NamedEntity objects sorted by confidence descending.
    """
    best: Dict[str, NamedEntity] = {}
    for entity in entities:
        key = f"{entity.entity_type.value}::{entity.text.lower()}"
        if key not in best or entity.confidence > best[key].confidence:
            best[key] = entity
    return sorted(best.values(), key=lambda e: e.confidence, reverse=True)


def deduplicate_strings(items: List[str]) -> List[str]:
    """
    Deduplicate a list of strings using case-insensitive normalization.

    Preserves the original casing of the first occurrence.

    Args:
        items: List of strings (references, sections, etc.)

    Returns:
        Deduplicated list preserving original casing of first occurrence.
    """
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        normalized = re.sub(r"\s+", " ", item.strip()).lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(item.strip())
    return result


def aggregate_keywords(all_chunk_keywords: List[List[str]], top_n: int = 20) -> List[str]:
    """
    Aggregate keyword lists from multiple chunks into a document-level top-N list.

    Uses frequency across all chunks to rank keywords at the document level.

    Args:
        all_chunk_keywords: List of keyword lists (one per chunk).
        top_n:              Maximum number of keywords to return.

    Returns:
        Top-N keywords by cross-chunk frequency.
    """
    counter: Counter = Counter()
    for chunk_keywords in all_chunk_keywords:
        counter.update(chunk_keywords)

    top_items = counter.most_common(top_n)
    top_items.sort(key=lambda x: (-x[1], x[0]))
    return [word for word, _ in top_items]
