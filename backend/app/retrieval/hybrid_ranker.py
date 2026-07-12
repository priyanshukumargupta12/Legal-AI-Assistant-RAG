"""
app/retrieval/hybrid_ranker.py
================================
Weighted Rank Fusion (WRF) algorithm for combining vector + BM25 results.

PURPOSE:
    Implements the Weighted Rank Fusion algorithm that:
        1. Collects all unique chunks from both vector and BM25 result lists.
        2. Normalises each score set independently to [0, 1].
        3. Combines them as: hybrid_score = (w_v × norm_vector) + (w_bm25 × norm_bm25)
        4. Sorts the final list by hybrid_score descending.
        5. Returns the top-N candidates.

WHY WEIGHTED RANK FUSION (WRF) over pure RRF?
----------------------------------------------
- **Score preservation:** WRF uses normalised raw scores rather than rank
  positions, preserving the magnitude of relevance within each result set.
- **Tunable weights:** The 70/30 default (vector/BM25) reflects the general
  superiority of semantic search for legal Q&A while keeping BM25 influence
  for exact-term legal codes.
- **No k constant needed:** Unlike RRF which requires tuning the k constant,
  WRF normalisation is parameter-free beyond the weights themselves.

WHY RANK FUSION IMPROVES ACCURACY:
    - A document that ranks #3 in vector search and #1 in BM25 should outscore
      a document that ranks #1 in vector but #10 in BM25.
    - Fusion rewards chunks that are relevant by BOTH retrieval methods,
      which strongly correlates with true relevance for legal Q&A.

FORMULA:
    norm_vector_i = (vector_score_i - min_v) / (max_v - min_v)   [or 0.0 if absent]
    norm_bm25_i   = (bm25_score_i - min_b) / (max_b - min_b)     [or 0.0 if absent]
    hybrid_score_i = (vector_weight × norm_vector_i) + (bm25_weight × norm_bm25_i)

SOLID: Single Responsibility — fusion algorithm only.
       Pure function — no state, no side effects.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.models.document import RetrievedChunk
from app.retrieval.retrieval_logger import retrieval_log
from app.retrieval.retrieval_models import FusionCandidate

# ── Default fusion weights ─────────────────────────────────────────────────────
DEFAULT_VECTOR_WEIGHT: float = 0.7
DEFAULT_BM25_WEIGHT: float = 0.3


def _normalize_scores(scores: List[float]) -> List[float]:
    """
    Min-max normalise a list of scores to [0, 1].

    If all scores are identical (zero range), returns a list of 1.0 values
    so no retriever is completely silenced.

    Args:
        scores: Raw score values from a retriever.

    Returns:
        Normalised scores in [0, 1].
    """
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    rng = max_s - min_s
    if rng == 0.0:
        return [1.0] * len(scores)
    return [(s - min_s) / rng for s in scores]


class WeightedRankFuser:
    """
    Weighted Rank Fusion for combining vector and BM25 retrieval results.

    The fuser collects all unique chunks from both result lists, normalises
    scores from each retriever independently, then computes a weighted
    linear combination as the final hybrid score.

    Args:
        vector_weight: Weight for vector (semantic) scores (default: 0.7).
        bm25_weight:   Weight for BM25 keyword scores (default: 0.3).
    """

    def __init__(
        self,
        vector_weight: float = DEFAULT_VECTOR_WEIGHT,
        bm25_weight: float = DEFAULT_BM25_WEIGHT,
        rrf_k: float = 60.0,
    ) -> None:
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.rrf_k = rrf_k

    def fuse(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[RetrievedChunk],
        top_n: Optional[int] = None,
    ) -> List[FusionCandidate]:
        """
        Merge and rank vector + BM25 results using Weighted Rank Fusion.

        Steps:
            1. Build a candidate pool: chunk_id → FusionCandidate.
            2. Populate vector_score and vector_rank from Qdrant results.
            3. Populate bm25_score and bm25_rank from Elasticsearch results.
            4. Normalise vector scores and BM25 scores independently.
            5. Compute hybrid_score = (w_v × norm_v) + (w_b × norm_b).
            6. Sort descending by hybrid_score.
            7. Return top_n candidates.

        Args:
            vector_results: Ranked list of chunks from Qdrant.
            bm25_results:   Ranked list of chunks from Elasticsearch.
            top_n:          Maximum number of candidates to return (None = all).

        Returns:
            Ranked list of ``FusionCandidate`` objects with hybrid_score set.
        """
        retrieval_log.info(
            "WRF fusion | vector_results={v} | bm25_results={b} | w_v={wv:.2f} | w_b={wb:.2f}",
            v=len(vector_results),
            b=len(bm25_results),
            wv=self.vector_weight,
            wb=self.bm25_weight,
        )

        # ── Step 1: Build candidate pool ──────────────────────────────────────
        pool: Dict[str, FusionCandidate] = {}

        for chunk in vector_results:
            key = chunk.chunk_id or f"{chunk.document_id}|{chunk.page_number}|{chunk.chunk_index}"
            if key not in pool:
                pool[key] = FusionCandidate(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    category=chunk.category,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                )
            pool[key].vector_score = chunk.score
            pool[key].vector_rank = chunk.rank

        for chunk in bm25_results:
            key = chunk.chunk_id or f"{chunk.document_id}|{chunk.page_number}|{chunk.chunk_index}"
            if key not in pool:
                pool[key] = FusionCandidate(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    category=chunk.category,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                )
            pool[key].bm25_score = chunk.score
            pool[key].bm25_rank = chunk.rank

        candidates = list(pool.values())

        # ── Step 2: Compute Reciprocal Rank Fusion (RRF) Scores ────────────────
        # RRF formula: hybrid_score = (0.5 / (k + vector_rank)) + (0.5 / (k + bm25_rank))
        # This provides robust rank-based fusion, ensuring top keyword hits aren't silenced by dense baseline scores.
        for cand in candidates:
            v_rr = 1.0 / (self.rrf_k + cand.vector_rank) if cand.vector_rank is not None else 0.0
            b_rr = 1.0 / (self.rrf_k + cand.bm25_rank) if cand.bm25_rank is not None else 0.0
            
            # Equal-weighted RRF
            cand.hybrid_score = (0.5 * v_rr) + (0.5 * b_rr)

        # ── Step 3: Sort descending by hybrid_score ────────────────────────────
        candidates.sort(key=lambda c: c.hybrid_score, reverse=True)

        # ── Step 4: Apply top-N cutoff ─────────────────────────────────────────
        if top_n is not None:
            candidates = candidates[:top_n]

        retrieval_log.info(
            "RRF fusion complete | candidates={total} | returning={n}",
            total=len(pool),
            n=len(candidates),
        )
        return candidates
