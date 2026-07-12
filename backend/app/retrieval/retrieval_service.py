"""
app/retrieval/retrieval_service.py
=====================================
Orchestration service for the Hybrid Retrieval Engine.

PURPOSE:
    Coordinates the full retrieval pipeline:
        1. Preprocess and validate the user query.
        2. Generate a query embedding vector (via BGEEmbedder).
        3. Fire vector and BM25 searches in parallel.
        4. Fuse results using Weighted Rank Fusion.
        5. Apply metadata post-filters.
        6. Remove duplicates.
        7. Select top-K candidates.
        8. Log and return structured results.

DESIGN:
    - Depends on ``HybridRetrievalRepository``, ``BGEEmbedder``, and
      ``WeightedRankFuser`` — all injected via constructor.
    - Returns ``HybridRetrievalResult`` domain object (not Pydantic schema).
    - Gracefully handles partial failures: if one retriever is down, returns
      results from the other with a warning in the log.

SOLID:
    Single Responsibility — orchestration only; delegates I/O to repository.
    Dependency Inversion  — depends on abstractions, not concretions.
"""

from __future__ import annotations

import time
from typing import List, Optional

from app.core.exceptions import RetrievalError
from app.embeddings.embedder import BGEEmbedder
from app.retrieval.duplicate_remover import remove_duplicate_candidates
from app.retrieval.hybrid_ranker import WeightedRankFuser
from app.retrieval.metadata_filter import filter_fusion_candidates
from app.retrieval.query_preprocessor import clean_and_validate
from app.retrieval.retrieval_logger import retrieval_log
from app.retrieval.retrieval_models import (
    FusionCandidate,
    HybridRetrievalResult,
    RetrievalQuery,
)
from app.retrieval.retrieval_repository import HybridRetrievalRepository
from app.retrieval.retrieval_utils import log_candidates_table


class HybridRetrievalService:
    """
    Orchestration service for the Hybrid Retrieval Engine.

    Accepts a raw user query, runs the full retrieval pipeline, and returns a
    structured ``HybridRetrievalResult`` containing the top-K ranked chunks.

    Args:
        repository:    ``HybridRetrievalRepository`` (Qdrant + ES).
        embedder:      ``BGEEmbedder`` for query vector generation.
        fuser:         ``WeightedRankFuser`` for combining results.
        retrieval_top_k:   Number of results per retriever (default: 10).
        final_top_k:       Final top-K after fusion (default: 5).
    """

    def __init__(
        self,
        repository: HybridRetrievalRepository,
        embedder: BGEEmbedder,
        fuser: WeightedRankFuser,
        retrieval_top_k: int = 10,
        final_top_k: int = 5,
        use_reranker: bool = False,
        rerank_model_name: str = "BAAI/bge-reranker-base",
        cache_dir: str | None = None,
    ) -> None:
        self._repo = repository
        self._embedder = embedder
        self._fuser = fuser
        self._retrieval_top_k = retrieval_top_k
        self._final_top_k = final_top_k
        self._use_reranker = use_reranker
        self._reranker = None
        if use_reranker and rerank_model_name:
            try:
                from sentence_transformers import CrossEncoder
                retrieval_log.info("Loading CrossEncoder reranker model: {model}", model=rerank_model_name)
                self._reranker = CrossEncoder(
                    rerank_model_name,
                    max_length=512,
                    device="cpu",
                    cache_folder=cache_dir
                )
                retrieval_log.info("CrossEncoder reranker model loaded successfully.")
            except Exception as e:
                retrieval_log.error("Failed to load CrossEncoder reranker | error={err}", err=str(e))
                self._use_reranker = False

    async def retrieve(
        self,
        raw_query: str,
        top_k: Optional[int] = None,
        final_top_k: Optional[int] = None,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None,
        fuzzy: bool = False,
    ) -> HybridRetrievalResult:
        """
        Execute the full hybrid retrieval pipeline for a user query.

        Pipeline:
            1. Preprocess + validate query
            2. Generate query embedding
            3. Parallel vector + BM25 search
            4. Weighted Rank Fusion
            5. Duplicate removal
            6. Metadata post-filter (if any applied)
            7. Top-K selection
            8. Return HybridRetrievalResult

        Args:
            raw_query:       Raw user query string.
            top_k:           Results per retriever (overrides constructor default).
            final_top_k:     Final top-K after fusion (overrides default).
            category_filter: Optional legal category filter.
            document_filter: Optional document_id filter.
            fuzzy:           Enable BM25 fuzzy matching.

        Returns:
            ``HybridRetrievalResult`` with ranked ``FusionCandidate`` objects.

        Raises:
            RetrievalError: If both retrievers fail or preprocessing fails.
        """
        start_time = time.perf_counter()
        k = top_k or self._retrieval_top_k
        final_k = final_top_k or self._final_top_k

        # ── Step 1: Preprocess & validate ──────────────────────────────────────
        try:
            clean_query = clean_and_validate(raw_query, log=True)
        except ValueError as exc:
            raise RetrievalError(f"Query validation failed: {exc}") from exc

        retrieval_log.info(
            "Retrieval start | query={q} | top_k={k} | final_k={fk} | cat={cat}",
            q=clean_query[:80],
            k=k,
            fk=final_k,
            cat=category_filter or "all",
        )

        # ── Step 2: Generate query embedding ──────────────────────────────────
        try:
            t_emb = time.perf_counter()
            query_vector = self._embedder.embed_query(clean_query)
            emb_ms = (time.perf_counter() - t_emb) * 1000
            retrieval_log.info(
                "Query embedded | dim={dim} | latency={lat:.1f}ms",
                dim=len(query_vector),
                lat=emb_ms,
            )
        except Exception as exc:
            retrieval_log.error("Query embedding failed | error={err}", err=str(exc))
            raise RetrievalError(f"Failed to embed query: {exc}") from exc

        # ── Step 3: Parallel search ────────────────────────────────────────────
        vector_results, bm25_results = await self._repo.parallel_search(
            query_vector=query_vector,
            query_text=clean_query,
            top_k=k,
            category_filter=category_filter,
            document_filter=document_filter,
            fuzzy=fuzzy,
        )

        retrieval_log.info(
            "Search results | vector={v} | bm25={b}",
            v=len(vector_results),
            b=len(bm25_results),
        )

        # Guard: if both retrievers returned nothing, return empty result
        if not vector_results and not bm25_results:
            retrieval_log.warning("Both retrievers returned no results for query: {q}", q=clean_query)
            elapsed = (time.perf_counter() - start_time) * 1000
            return HybridRetrievalResult(
                query=clean_query,
                results=[],
                vector_count=0,
                bm25_count=0,
                total_candidates=0,
                retrieval_time_ms=round(elapsed, 2),
            )

        # ── Step 4: Weighted Rank Fusion ───────────────────────────────────────
        candidates: List[FusionCandidate] = self._fuser.fuse(
            vector_results=vector_results,
            bm25_results=bm25_results,
            top_n=None,  # get all candidates before dedup
        )

        total_before_dedup = len(candidates)

        # ── Step 5: Duplicate removal ──────────────────────────────────────────
        candidates = remove_duplicate_candidates(candidates)

        # ── Step 6: Metadata post-filter ──────────────────────────────────────
        # Note: pre-filters are already applied in the repository layer.
        # Post-filter here catches any edge cases where pre-filter was partial.
        if category_filter or document_filter:
            candidates = filter_fusion_candidates(
                candidates,
                category_filter=category_filter,
                document_filter=document_filter,
            )

        # ── Step 6.5: Cross-Encoder Reranking ──────────────────────────────────
        if self._use_reranker and self._reranker and candidates:
            try:
                pairs = [(clean_query, cand.text) for cand in candidates]
                scores = self._reranker.predict(pairs)
                for cand, score in zip(candidates, scores):
                    cand.hybrid_score = float(score)
                # Re-sort candidates based on Cross-Encoder relevance score
                candidates.sort(key=lambda c: c.hybrid_score, reverse=True)
                retrieval_log.info("Cross-Encoder reranking complete | candidates_scored={n}", n=len(candidates))
            except Exception as exc:
                retrieval_log.error("Cross-Encoder reranking failed | error={err}", err=str(exc))

        # ── Step 7: Top-K selection ────────────────────────────────────────────
        final_candidates = candidates[:final_k]

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        retrieval_log.info(
            "Retrieval complete | query={q} | returned={n} | time={t:.1f}ms",
            q=clean_query[:80],
            n=len(final_candidates),
            t=elapsed_ms,
        )

        # Log the final ranked table
        log_candidates_table(final_candidates, label=f"Top {len(final_candidates)} Results")

        return HybridRetrievalResult(
            query=clean_query,
            results=final_candidates,
            vector_count=len(vector_results),
            bm25_count=len(bm25_results),
            total_candidates=total_before_dedup,
            retrieval_time_ms=round(elapsed_ms, 2),
        )

    async def health_check(self) -> dict:
        """Return health status of both underlying retrievers."""
        return await self._repo.health_check()
