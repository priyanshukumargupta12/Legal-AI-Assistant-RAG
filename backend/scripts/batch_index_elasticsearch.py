"""
scripts/batch_index_elasticsearch.py
======================================
Batch Indexing: Index all chunked documents into Elasticsearch.

PURPOSE:
    Scans the metadata/chunks/ folder for all chunked JSON files,
    loads chunks for each document, validates them, and bulk-indexes
    them into the configured Elasticsearch index (legal_documents).

USAGE:
    From the backend directory:
        python scripts/batch_index_elasticsearch.py

PREREQUISITES:
    1. Run the chunking pipeline first:
           python scripts/batch_parse_and_chunk.py
    2. Ensure ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY are set in .env
    3. The virtual environment must have elasticsearch>=8.14.0 installed.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Ensure backend root is on the Python path ──────────────────────────────────
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.elasticsearch.elastic_client import get_elasticsearch_client
from app.elasticsearch.elastic_logger import elastic_log
from app.elasticsearch.elastic_models import ElasticsearchStatistics
from app.elasticsearch.elastic_repository import ElasticsearchRepository
from app.elasticsearch.elastic_service import ElasticsearchService


def run_batch_indexing() -> None:
    """
    Main entry point for the batch Elasticsearch indexing run.

    Steps:
        1. Discover all chunk JSON files in metadata/chunks/.
        2. Initialise the Elasticsearch client and ensure the index exists.
        3. For each document, load chunks and bulk-index them.
        4. Print per-document progress and final summary.
        5. Persist run statistics to metadata/elasticsearch_statistics.json.
    """
    settings = get_settings()
    chunks_dir = Path(settings.metadata_path) / "chunks"

    print("=" * 80)
    print("         BATCH ELASTICSEARCH INDEXING PIPELINE")
    print("=" * 80)
    print(f"  * Elasticsearch URL  : {settings.elasticsearch_url}")
    print(f"  * Index Name         : {settings.elasticsearch_index_name}")
    print(f"  * Bulk Batch Size    : {settings.elasticsearch_bulk_batch_size}")
    print(f"  * Refresh Interval   : {settings.elasticsearch_refresh_interval}")
    print(f"  * Chunks Dir         : {chunks_dir}")
    print("=" * 80)

    # ── 1. Discover chunk files ────────────────────────────────────────────────
    if not chunks_dir.exists():
        print(f"[ERROR] Chunks directory not found: {chunks_dir}")
        print("        Run the chunking pipeline first.")
        sys.exit(1)

    chunk_files = sorted(chunks_dir.glob("*_chunks.json"))
    total_docs = len(chunk_files)

    if total_docs == 0:
        print(f"[WARNING] No chunk JSON files found in {chunks_dir}.")
        return

    print(f"\nDiscovered {total_docs} document chunk files to index.\n")

    # ── 2. Initialise services ─────────────────────────────────────────────────
    print("Initialising Elasticsearch services...")
    try:
        es_client = get_elasticsearch_client(settings)
    except Exception as exc:
        print(f"[ERROR] Cannot connect to Elasticsearch: {exc}")
        sys.exit(1)

    repository = ElasticsearchRepository(client=es_client, settings=settings)
    service = ElasticsearchService(
        repository=repository,
        metadata_dir=Path(settings.metadata_path),
    )

    # ── 3. Create index ────────────────────────────────────────────────────────
    print("Ensuring Elasticsearch index exists...")
    try:
        created = service.ensure_index()
        status = "CREATED" if created else "ALREADY EXISTS"
        print(f"  Index '{settings.elasticsearch_index_name}': {status}\n")
    except Exception as exc:
        print(f"[ERROR] Failed to create index: {exc}")
        sys.exit(1)

    # ── 4. Process each document ───────────────────────────────────────────────
    total_chunks_attempted = 0
    total_chunks_indexed = 0
    total_chunks_failed = 0

    global_start = time.perf_counter()
    print("Starting batch indexing...\n")

    for idx, chunk_file in enumerate(chunk_files, start=1):
        doc_id = chunk_file.name.replace("_chunks.json", "")
        doc_name = doc_id

        # Read filename from metadata envelope if available
        try:
            with open(chunk_file, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict) and "metadata" in raw:
                doc_name = raw["metadata"].get("document_name", doc_id)
        except Exception:
            pass

        print(f"[{idx:3d}/{total_docs}] Indexing: {doc_name}")
        t0 = time.perf_counter()

        try:
            chunks = service.load_chunks_for_document(doc_id)
            total_chunks_attempted += len(chunks)

            # Synchronous bulk indexing (no event loop needed)
            result = repository._index_chunks_sync(chunks)
            indexed = result["indexed"]
            failed = result["failed"]

            total_chunks_indexed += indexed
            total_chunks_failed += failed

            elapsed = time.perf_counter() - t0
            print(
                f"      Success | Chunks: {len(chunks):,} "
                f"| Indexed: {indexed:,} "
                f"| Failed: {failed:,} "
                f"| Time: {elapsed:.2f}s"
            )

        except FileNotFoundError as exc:
            elapsed = time.perf_counter() - t0
            print(f"      [SKIP] File not found: {exc} | Time: {elapsed:.2f}s")

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"      [FAILED] Error: {exc} | Time: {elapsed:.2f}s")
            total_chunks_failed += 1

    # ── 5. Print summary ───────────────────────────────────────────────────────
    total_duration = time.perf_counter() - global_start
    avg_ms = (
        (total_duration / total_chunks_attempted) * 1000
        if total_chunks_attempted > 0
        else 0.0
    )

    # Fetch index stats from ES
    try:
        idx_stats = service.get_index_stats()
        doc_count = idx_stats.get("doc_count", "N/A")
        store_bytes = idx_stats.get("store_size_bytes", 0)
        store_mb = round(store_bytes / 1024 / 1024, 2) if store_bytes else 0
    except Exception:
        doc_count = "N/A"
        store_mb = "N/A"

    print("\n" + "=" * 80)
    print("         BATCH ELASTICSEARCH INDEXING COMPLETE")
    print("=" * 80)
    print(f"  Documents processed      : {total_docs}")
    print(f"  Total chunks attempted   : {total_chunks_attempted:,}")
    print(f"  Total chunks indexed     : {total_chunks_indexed:,}")
    print(f"  Total chunks failed      : {total_chunks_failed:,}")
    print(f"  Total duration           : {total_duration / 60:.2f} minutes ({total_duration:.1f}s)")
    print(f"  Grand average per chunk  : {avg_ms:.1f} ms")
    print(f"  Elasticsearch doc count  : {doc_count:,}" if isinstance(doc_count, int) else f"  Elasticsearch doc count  : {doc_count}")
    print(f"  Index store size         : {store_mb} MB")
    print("=" * 80)

    # ── 6. Save statistics ─────────────────────────────────────────────────────
    stats = ElasticsearchStatistics(
        total_chunks=total_chunks_attempted,
        indexed_chunks=total_chunks_indexed,
        failed_chunks=total_chunks_failed,
        index_name=settings.elasticsearch_index_name,
        total_duration_s=total_duration,
        avg_chunk_time_ms=avg_ms,
        processed_at=datetime.now(timezone.utc),
    )
    stats_path = service.save_statistics(stats)
    print(f"  Statistics saved to      : {stats_path}")
    print("=" * 80)


if __name__ == "__main__":
    run_batch_indexing()
