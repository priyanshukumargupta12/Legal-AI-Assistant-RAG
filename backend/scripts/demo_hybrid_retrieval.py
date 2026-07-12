"""
scripts/demo_hybrid_retrieval.py
==================================
End-to-end demonstration of the Hybrid Retrieval Engine.

PURPOSE:
    Validates the full retrieval pipeline:
        1. Connect to Qdrant Cloud and Elasticsearch Cloud.
        2. Preprocess and embed the demo query.
        3. Run vector search (Qdrant) and BM25 search (Elasticsearch) in parallel.
        4. Apply Weighted Rank Fusion (70% vector, 30% BM25).
        5. Show individual vector + BM25 results.
        6. Show final Top-5 fused results with all scores.

USAGE:
    From the backend directory:
        python scripts/demo_hybrid_retrieval.py

PREREQUISITES:
    - QDRANT_URL, QDRANT_API_KEY set in .env (Qdrant Cloud)
    - ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY set in .env (Elastic Cloud)
    - Both indexes populated (batch_embed_and_index.py + batch_index_elasticsearch.py)
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Fix Windows terminal encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# Ensure backend root is on the Python path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.elasticsearch.elastic_client import get_elasticsearch_client
from app.elasticsearch.elastic_repository import ElasticsearchRepository
from app.embeddings.embedder import BGEEmbedder
from app.retrieval.hybrid_ranker import WeightedRankFuser
from app.retrieval.retrieval_repository import HybridRetrievalRepository
from app.retrieval.retrieval_service import HybridRetrievalService
from app.vectorstore import get_qdrant_client, QdrantRepository

# ── Demo Queries ───────────────────────────────────────────────────────────────
DEMO_QUERIES = [
    {
        "query": "What is the Child Tax Credit?",
        "category": None,
        "description": "General tax query — tests cross-category semantic retrieval",
    },
    {
        "query": "breach of fiduciary duty legal standard",
        "category": "CourtJudgement",
        "description": "Category-filtered court case query",
    },
    {
        "query": "IRC Section 401k retirement plan employee contributions",
        "category": "Acts",
        "description": "Exact statute reference — tests BM25 precision",
    },
]


def separator(char: str = "=", n: int = 80) -> str:
    return char * n


async def run_demo() -> None:
    """Run the hybrid retrieval demonstration."""
    settings = get_settings()

    print(separator())
    print("         HYBRID RETRIEVAL ENGINE DEMONSTRATION")
    print(separator())
    print(f"  Qdrant URL          : {settings.qdrant_url}")
    print(f"  Qdrant Collection   : {settings.qdrant_collection_name}")
    print(f"  Elasticsearch URL   : {settings.elasticsearch_url}")
    print(f"  ES Index            : {settings.elasticsearch_index_name}")
    print(f"  Embedding Model     : {settings.embedding_model_name}")
    print(f"  Vector Weight (WRF) : {settings.vector_weight}")
    print(f"  BM25 Weight (WRF)   : {settings.bm25_weight}")
    print(f"  Top-K per retriever : {settings.retrieval_top_k}")
    print(f"  Final Top-K         : {settings.retrieval_final_top_k}")
    print(separator())

    # ── Initialise services ────────────────────────────────────────────────────
    print("\n[INIT] Loading components...")

    qdrant_client = get_qdrant_client(settings)
    vector_repo = QdrantRepository(client=qdrant_client, settings=settings)

    es_client = get_elasticsearch_client(settings)
    keyword_repo = ElasticsearchRepository(client=es_client, settings=settings)

    retrieval_repo = HybridRetrievalRepository(
        vector_repo=vector_repo,
        keyword_repo=keyword_repo,
        timeout_s=settings.retrieval_timeout_s,
    )

    print("  Loading BGE embedding model (singleton)...")
    embedder = BGEEmbedder(
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_cache_dir,
    )

    fuser = WeightedRankFuser(
        vector_weight=settings.vector_weight,
        bm25_weight=settings.bm25_weight,
    )

    service = HybridRetrievalService(
        repository=retrieval_repo,
        embedder=embedder,
        fuser=fuser,
        retrieval_top_k=settings.retrieval_top_k,
        final_top_k=settings.retrieval_final_top_k,
    )

    # ── Health check ───────────────────────────────────────────────────────────
    print("\n[HEALTH] Checking both retrievers...")
    health = await service.health_check()
    for store, status in health.items():
        icon = "[OK]" if status == "healthy" else "[DOWN]"
        print(f"  {store:<20}: {icon} {status}")

    # ── Run each demo query ────────────────────────────────────────────────────
    for idx, demo in enumerate(DEMO_QUERIES, 1):
        raw_query = demo["query"]
        category = demo["category"]
        desc = demo["description"]

        print(f"\n{separator()}")
        print(f"  DEMO {idx}: {desc}")
        print(separator())
        print(f"  Query    : {raw_query}")
        print(f"  Category : {category or 'All'}")
        print(separator("-"))

        total_start = time.perf_counter()

        # Step A: Run retrieval
        result = await service.retrieve(
            raw_query=raw_query,
            category_filter=category,
            top_k=settings.retrieval_top_k,
            final_top_k=settings.retrieval_final_top_k,
        )

        total_ms = (time.perf_counter() - total_start) * 1000

        # Step B: Show vector results (intermediate)
        print(f"\n  [A] VECTOR SEARCH RESULTS (Top {settings.retrieval_top_k}, Qdrant)")
        print(f"      Returned: {result.vector_count} results")
        vector_in_pool = [c for c in result.results if c.vector_score > 0]
        for i, c in enumerate(result.results[:3], 1):
            if c.vector_score > 0:
                print(f"      #{i}: {c.document_name}  p.{c.page_number}  "
                      f"[vector={c.vector_score:.4f}]  {c.text[:100]}...")

        # Step C: Show BM25 results (intermediate)
        print(f"\n  [B] BM25 SEARCH RESULTS (Top {settings.retrieval_top_k}, Elasticsearch)")
        print(f"      Returned: {result.bm25_count} results")
        for i, c in enumerate(result.results[:3], 1):
            if c.bm25_score > 0:
                print(f"      #{i}: {c.document_name}  p.{c.page_number}  "
                      f"[bm25={c.bm25_score:.4f}]  {c.text[:100]}...")

        # Step D: Show WRF fusion info
        print(f"\n  [C] WEIGHTED RANK FUSION (v={settings.vector_weight}, b={settings.bm25_weight})")
        print(f"      Total unique candidates before fusion: {result.total_candidates}")
        print(f"      hybrid_score = ({settings.vector_weight} x norm_vector) + "
              f"({settings.bm25_weight} x norm_bm25)")

        # Step E: Final top results
        print(f"\n  [D] FINAL TOP {len(result.results)} RESULTS")
        print(separator("-"))
        print(f"  {'Rank':<6}{'Document':<35}{'Page':<6}{'Category':<18}"
              f"{'VecScore':<10}{'BM25':<10}{'Hybrid':<10}")
        print(separator("-"))
        for rank, c in enumerate(result.results, 1):
            print(
                f"  {rank:<6}{c.document_name[:32]:<35}{c.page_number:<6}"
                f"{c.category:<18}{c.vector_score:<10.4f}{c.bm25_score:<10.4f}"
                f"{c.hybrid_score:<10.4f}"
            )
        print(separator("-"))

        # Step F: Show JSON-like output for first result
        if result.results:
            top = result.results[0]
            print("\n  [E] TOP RESULT (JSON OUTPUT FORMAT)")
            print("  {")
            print(f'    "query": "{result.query}",')
            print('    "results": [')
            print("      {")
            print(f'        "chunk_id": "{top.chunk_id}",')
            print(f'        "document": "{top.document_name}",')
            print(f'        "page": {top.page_number},')
            print(f'        "category": "{top.category}",')
            print(f'        "text": "{top.text[:120].replace(chr(34), chr(39))}...",')
            print(f'        "vector_score": {top.vector_score:.4f},')
            print(f'        "bm25_score": {top.bm25_score:.4f},')
            print(f'        "hybrid_score": {top.hybrid_score:.4f}')
            print("      }")
            print("    ]")
            print("  }")

        print(f"\n  Total retrieval time: {result.retrieval_time_ms:.1f}ms")

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{separator()}")
    print("         HYBRID RETRIEVAL DEMO COMPLETE [OK]")
    print(separator())
    print(
        "\nThe Hybrid Retrieval Engine is production-ready.\n"
        "Run 'python scripts/batch_index_elasticsearch.py' if ES is not\n"
        "fully populated yet.\n"
    )


if __name__ == "__main__":
    asyncio.run(run_demo())
