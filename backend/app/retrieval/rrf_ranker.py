"""
app/retrieval/rrf_ranker.py
=============================
Reciprocal Rank Fusion (RRF) algorithm implementation.

PURPOSE:
    Stateless utility that merges two ranked lists (vector + BM25 results)
    into a single unified ranked list using RRF scoring.

    RRF is kept as an alternative fusion strategy alongside ``WeightedRankFuser``.
    Both are available; the service layer defaults to WRF with configurable weights
    but can be swapped to RRF for parameter-free operation.

FORMULA:
    RRF(d) = sum_i( 1 / (k + rank_i(d)) )   where k=60 (default)

WHY RRF:
    - Parameter-robust: k=60 works well without tuning in most IR benchmarks.
    - No score normalisation required — uses rank positions, not raw scores.
    - Standard in information retrieval research (Cormack et al. 2009).
    - Gracefully handles missing retrievers: absent chunks get rank=∞ → score≈0.

WHY WRF IS PREFERRED HERE:
    - WRF preserves score magnitude, allowing the 70% vector / 30% BM25 split
      to reflect the relative reliability of each retriever.
    - RRF treats all ranks equally regardless of score gaps (e.g., rank #1 with
      score 0.95 and rank #1 with score 0.31 are indistinguishable under RRF).

SOLID: Single Responsibility — RRF algorithm only.
       Pure function — no state, no side effects.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.models.document import RetrievedChunk
from app.retrieval.retrieval_logger import retrieval_log
from app.retrieval.retrieval_models import FusionCandidate

# ── Default RRF constant ───────────────────────────────────────────────────────
DEFAULT_RRF_K: int = 60


class RRFRanker:
    """
    Stateless Reciprocal Rank Fusion merger.

    Merges two ranked retrieval result lists (vector + BM25) into a single
    ranked list using the standard RRF formula.

    Args:
        k: RRF robustness constant (default: 60). Higher k = more smoothing.
    """

    def __init__(self, k: int = DEFAULT_RRF_K) -> None:
        self.k = k

    @staticmethod
    def _compute_rrf_score(rank: int, k: int) -> float:
        """
        Compute the RRF contribution score for a document at position ``rank``.

        Args:
            rank: 1-indexed rank position.
            k:    RRF robustness constant.

        Returns:
            Float RRF contribution score (always positive, decreasing with rank).
        """
        if rank <= 0:
            return 0.0
        return 1.0 / (k + rank)

    def merge(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[RetrievedChunk],
        top_n: Optional[int] = None,
    ) -> List[FusionCandidate]:
        """
        Merge and rank vector + BM25 results using Reciprocal Rank Fusion.

        For each unique chunk:
            rrf_score = 1/(k + vector_rank) + 1/(k + bm25_rank)
        Chunks absent from a retriever receive rank=∞ → RRF contribution=0.

        Args:
            vector_results: Ranked list of chunks from Qdrant.
            bm25_results:   Ranked list of chunks from Elasticsearch.
            top_n:          Maximum candidates to return (None = all).

        Returns:
            List of ``FusionCandidate`` objects sorted by hybrid_score.
        """
        retrieval_log.info(
            "RRF merge | vector_results={v} | bm25_results={b} | k={k}",
            v=len(vector_results),
            b=len(bm25_results),
            k=self.k,
        )

        # ── Build candidate pool ───────────────────────────────────────────────
        pool: Dict[str, FusionCandidate] = {}

        # Process vector results
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

        # Process BM25 results
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

        # ── Compute RRF scores ─────────────────────────────────────────────────
        candidates = list(pool.values())
        for cand in candidates:
            rrf_v = self._compute_rrf_score(cand.vector_rank, self.k)
            rrf_b = self._compute_rrf_score(cand.bm25_rank, self.k)
            cand.hybrid_score = rrf_v + rrf_b

        # ── Sort and truncate ──────────────────────────────────────────────────
        candidates.sort(key=lambda c: c.hybrid_score, reverse=True)
        if top_n is not None:
            candidates = candidates[:top_n]

        retrieval_log.info(
            "RRF merge complete | candidates={total} | returning={n}",
            total=len(pool),
            n=len(candidates),
        )
        return candidates
