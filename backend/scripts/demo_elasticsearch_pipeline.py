"""
scripts/demo_elasticsearch_pipeline.py
========================================
Demonstration script for the Elasticsearch Pipeline.

PURPOSE:
    End-to-end validation of the Elasticsearch module:
        1. Connect to Elasticsearch (Elastic Cloud or local).
        2. Auto-create the index with legal_analyzer mapping.
        3. Index a small set of sample legal chunks.
        4. Run BM25 search and return Top-5 results.
        5. Run a phrase search demonstration.
        6. Run a category-filtered search.
        7. Clean up sample data.

USAGE:
    From the backend directory:
        python scripts/demo_elasticsearch_pipeline.py

PREREQUISITES:
    - ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY set in .env
    - elasticsearch>=8.14.0 installed in venv
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# ── Ensure backend root is on the Python path ──────────────────────────────────
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Fix Windows terminal encoding for special characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from app.core.config import get_settings
from app.elasticsearch.elastic_client import get_elasticsearch_client
from app.elasticsearch.elastic_repository import ElasticsearchRepository
from app.elasticsearch.elastic_service import ElasticsearchService
from app.models.document import DocumentChunk

# ── Sample legal chunks for demonstration ─────────────────────────────────────
SAMPLE_CHUNKS = [
    DocumentChunk(
        chunk_id="demo-chunk-0001",
        document_id="demo-doc-001",
        document_name="IRS_Publication_17.pdf",
        category="Tax",
        page_number=42,
        chunk_index=0,
        text=(
            "Under Internal Revenue Code Section 162, taxpayers may deduct ordinary "
            "and necessary business expenses paid or incurred during the taxable year "
            "in carrying on any trade or business. The expense must be both ordinary "
            "— common and accepted in your field — and necessary — helpful and "
            "appropriate for your business."
        ),
        char_count=350,
        source="keyword",
        metadata={"year": "2023", "publication": "IRS Pub 17"},
    ),
    DocumentChunk(
        chunk_id="demo-chunk-0002",
        document_id="demo-doc-001",
        document_name="IRS_Publication_17.pdf",
        category="Tax",
        page_number=108,
        chunk_index=1,
        text=(
            "Capital gains and losses arise from the sale or exchange of capital assets. "
            "A capital asset includes property such as stocks, bonds, and real estate. "
            "The tax rate on long-term capital gains — held longer than one year — is "
            "generally lower than the ordinary income tax rate. Short-term capital gains "
            "are taxed at ordinary income rates."
        ),
        char_count=410,
        source="keyword",
        metadata={"year": "2023", "topic": "capital gains"},
    ),
    DocumentChunk(
        chunk_id="demo-chunk-0003",
        document_id="demo-doc-002",
        document_name="Court_011.pdf",
        category="CourtJudgement",
        page_number=5,
        chunk_index=0,
        text=(
            "The court held that the defendant breached its fiduciary duty to the "
            "plaintiff by failing to disclose material conflicts of interest. "
            "Fiduciary duty requires a party to act with the utmost good faith, "
            "loyalty, and care in managing the affairs of another. The breach caused "
            "quantifiable harm to the plaintiff, warranting compensatory damages."
        ),
        char_count=420,
        source="keyword",
        metadata={"court": "District Court", "year": "2022"},
    ),
    DocumentChunk(
        chunk_id="demo-chunk-0004",
        document_id="demo-doc-003",
        document_name="OLC_Opinion_036.pdf",
        category="Legal_opinion",
        page_number=12,
        chunk_index=0,
        text=(
            "The Office of Legal Counsel concludes that the President's authority to "
            "issue executive orders under Article II of the Constitution extends to "
            "directing federal agencies to adopt regulatory policies consistent with "
            "the administration's statutory interpretation. However, such orders may "
            "not contravene an explicit statutory directive from Congress."
        ),
        char_count=450,
        source="keyword",
        metadata={"issuer": "OLC", "year": "2021"},
    ),
    DocumentChunk(
        chunk_id="demo-chunk-0005",
        document_id="demo-doc-004",
        document_name="Title26_Vol9.pdf",
        category="Acts",
        page_number=231,
        chunk_index=0,
        text=(
            "Section 401(k) of the Internal Revenue Code permits employees to elect "
            "to have the employer contribute a portion of the employee's wages to an "
            "individual account. Contributions are made pre-tax, reducing the "
            "employee's current taxable income. Distributions from 401(k) accounts "
            "are taxed as ordinary income upon withdrawal."
        ),
        char_count=390,
        source="keyword",
        metadata={"volume": "Vol 9", "chapter": "26"},
    ),
]


async def run_demo() -> None:
    """
    Run the end-to-end Elasticsearch pipeline demonstration.
    """
    settings = get_settings()

    print("=" * 80)
    print("         ELASTICSEARCH PIPELINE DEMONSTRATION")
    print("=" * 80)
    print(f"  Elasticsearch URL : {settings.elasticsearch_url}")
    print(f"  Index Name        : {settings.elasticsearch_index_name}")
    print("=" * 80)

    # ── Step 1: Connect ────────────────────────────────────────────────────────
    print("\n[STEP 1] Connecting to Elasticsearch...")
    try:
        client = get_elasticsearch_client(settings)
    except Exception as exc:
        print(f"  [ERROR] Cannot connect: {exc}")
        sys.exit(1)

    repository = ElasticsearchRepository(client=client, settings=settings)
    service = ElasticsearchService(
        repository=repository,
        metadata_dir=Path(settings.metadata_path),
    )

    # ── Step 2: Health check ───────────────────────────────────────────────────
    print("[STEP 2] Running health check...")
    healthy = await service.health_check()
    if not healthy:
        print("  [ERROR] Elasticsearch is not reachable. Check credentials/URL.")
        sys.exit(1)
    print("  Elasticsearch is HEALTHY [OK]")

    # ── Step 3: Create index ───────────────────────────────────────────────────
    print(f"\n[STEP 3] Creating index '{settings.elasticsearch_index_name}'...")
    created = service.ensure_index()
    print(f"  Index {'CREATED [OK]' if created else 'already exists [OK]'}")

    # ── Step 4: Index sample chunks ────────────────────────────────────────────
    print(f"\n[STEP 4] Indexing {len(SAMPLE_CHUNKS)} sample legal chunks...")
    t0 = time.perf_counter()
    await repository.index_chunks(SAMPLE_CHUNKS)

    # Force refresh so documents are immediately searchable
    client.indices.refresh(index=settings.elasticsearch_index_name)
    elapsed = time.perf_counter() - t0
    print(f"  Indexed {len(SAMPLE_CHUNKS)} chunks in {elapsed:.2f}s [OK]")

    # ── Step 5: BM25 Search — Top 5 ───────────────────────────────────────────
    print("\n" + "─" * 80)
    print("[STEP 5] BM25 Search: 'business expense deduction tax'  (Top 5)")
    print("─" * 80)

    results = await service.keyword_search(
        query="business expense deduction tax",
        top_k=5,
    )
    _print_results(results)

    # ── Step 6: Phrase Search ──────────────────────────────────────────────────
    print("\n" + "─" * 80)
    print("[STEP 6] Exact Phrase Search: 'fiduciary duty'")
    print("─" * 80)

    results = await service.keyword_search(
        query="fiduciary duty",
        top_k=5,
    )
    _print_results(results)

    # ── Step 7: Category-filtered search ──────────────────────────────────────
    print("\n" + "─" * 80)
    print("[STEP 7] Category-Filtered Search: query='401k retirement' | category='Acts'")
    print("─" * 80)

    results = await service.keyword_search(
        query="401k retirement income",
        top_k=5,
        category_filter="Acts",
    )
    _print_results(results)

    # ── Step 8: Fuzzy search ───────────────────────────────────────────────────
    print("\n" + "─" * 80)
    print("[STEP 8] Fuzzy Search: 'capitl gain taxs' (intentional typos)")
    print("─" * 80)

    results = await service.keyword_search(
        query="capitl gain taxs",
        top_k=5,
        fuzzy=True,
    )
    _print_results(results)

    # ── Step 9: Index stats ────────────────────────────────────────────────────
    print("\n[STEP 9] Index Statistics")
    print("─" * 80)
    stats = service.get_index_stats()
    print(f"  Index Name        : {stats['index_name']}")
    print(f"  Document Count    : {stats['doc_count']}")
    print(f"  Store Size        : {stats['store_size_bytes'] / 1024:.1f} KB")

    # ── Step 10: Cleanup ───────────────────────────────────────────────────────
    print("\n[STEP 10] Cleaning up demo data...")
    for doc_id in {"demo-doc-001", "demo-doc-002", "demo-doc-003", "demo-doc-004"}:
        await repository.delete_by_document_id(doc_id)
    client.indices.refresh(index=settings.elasticsearch_index_name)
    print("  Demo chunks deleted [OK]")

    print("\n" + "=" * 80)
    print("         ELASTICSEARCH PIPELINE DEMO COMPLETE [OK]")
    print("=" * 80)
    print(
        "\nThe Elasticsearch module is fully operational.\n"
        "Run 'python scripts/batch_index_elasticsearch.py' to index all\n"
        "152,086 legal document chunks into Elasticsearch.\n"
    )


def _print_results(results) -> None:
    """Pretty-print BM25 search results."""
    if not results:
        print("  No results found.")
        return
    for r in results:
        print(f"\n  Rank #{r.rank}  |  Score: {r.score:.4f}")
        print(f"  Document : {r.document_name}  (Page {r.page_number})")
        print(f"  Category : {r.category}")
        excerpt = r.text[:200].replace("\n", " ")
        print(f"  Excerpt  : {excerpt}...")


if __name__ == "__main__":
    asyncio.run(run_demo())
