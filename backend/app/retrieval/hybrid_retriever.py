"""
app/retrieval/hybrid_retriever.py
====================================
Hybrid retriever facade — thin convenience wrapper over HybridRetrievalService.

PURPOSE:
    Provides a simple ``HybridRetriever`` class for callers (e.g., the LLM
    service) that do not want to construct the full service stack manually.
    Also replaces the empty stub from Milestone 6.

DESIGN:
    - Delegates to ``HybridRetrievalService.retrieve()`` entirely.
    - The constructor accepts the same dependencies as the service for
      consistency.
    - Exposes a single ``retrieve()`` method.

SOLID: Façade pattern — simplifies the interface for downstream consumers.
"""

from __future__ import annotations

from typing import List, Optional

from app.embeddings.embedder import BGEEmbedder
from app.retrieval.hybrid_ranker import WeightedRankFuser
from app.retrieval.retrieval_models import FusionCandidate, HybridRetrievalResult
from app.retrieval.retrieval_repository import HybridRetrievalRepository
from app.retrieval.retrieval_service import HybridRetrievalService


class HybridRetriever:
    """
    Convenience facade over ``HybridRetrievalService``.

    Fires vector + BM25 searches in parallel, applies Weighted Rank Fusion,
    and returns a ranked list of ``FusionCandidate`` objects.

    Args:
        repository:       ``HybridRetrievalRepository`` instance.
        embedder:         ``BGEEmbedder`` for query encoding.
        vector_weight:    Vector score weight for WRF (default: 0.7).
        bm25_weight:      BM25 score weight for WRF (default: 0.3).
        retrieval_top_k:  Results per retriever (default: 10).
        final_top_k:      Final top-K after fusion (default: 5).
    """

    def __init__(
        self,
        repository: HybridRetrievalRepository,
        embedder: BGEEmbedder,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        retrieval_top_k: int = 10,
        final_top_k: int = 5,
    ) -> None:
        fuser = WeightedRankFuser(
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )
        self._service = HybridRetrievalService(
            repository=repository,
            embedder=embedder,
            fuser=fuser,
            retrieval_top_k=retrieval_top_k,
            final_top_k=final_top_k,
        )

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        final_top_k: Optional[int] = None,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None,
        fuzzy: bool = False,
    ) -> HybridRetrievalResult:
        """
        Execute hybrid retrieval and return the full ``HybridRetrievalResult``.

        Args:
            query:           Raw user query string.
            top_k:           Results per retriever.
            final_top_k:     Final top-K after fusion.
            category_filter: Optional legal category filter.
            document_filter: Optional document_id filter.
            fuzzy:           Enable BM25 fuzzy matching.

        Returns:
            ``HybridRetrievalResult`` with ranked ``FusionCandidate`` list.
        """
        return await self._service.retrieve(
            raw_query=query,
            top_k=top_k,
            final_top_k=final_top_k,
            category_filter=category_filter,
            document_filter=document_filter,
            fuzzy=fuzzy,
        )
