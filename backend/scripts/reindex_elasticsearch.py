"""
scripts/reindex_elasticsearch.py
==================================
Standalone bulk-indexing script — connects to a fresh Elasticsearch Cloud
deployment and indexes all existing local chunks without re-parsing or
re-embedding any documents.

USAGE (from the backend/ directory with venv activated):
    python scripts/reindex_elasticsearch.py

WHAT IT DOES:
    1. Reads ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY from .env
    2. Pings the cluster to verify connectivity
    3. Creates the 'legal_documents' index (with the full legal_analyzer
       mapping) if it does not already exist
    4. Scans metadata/chunks/ for all *_chunks.json files
    5. Loads every chunk and bulk-indexes in batches of 200
    6. Prints final count + sample BM25 verification query

WHAT IT DOES NOT DO:
    - It does NOT call Gemini or any embedding API
    - It does NOT modify Qdrant
    - It does NOT re-parse or re-chunk PDFs
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# -- Ensure the backend/ package root is on sys.path --------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # backend/scripts/
BACKEND_DIR = SCRIPT_DIR.parent                        # backend/
sys.path.insert(0, str(BACKEND_DIR))

# -- Load .env before importing anything that needs env vars ------------------
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk as es_bulk


# =============================================================================
# CONFIGURATION -- read from .env
# =============================================================================

ES_URL      = os.environ.get("ELASTICSEARCH_URL", "").strip()
ES_API_KEY  = os.environ.get("ELASTICSEARCH_API_KEY", "").strip()
INDEX_NAME  = os.environ.get("ELASTICSEARCH_INDEX_NAME", "legal_documents").strip()
CHUNKS_DIR  = (BACKEND_DIR.parent / "metadata" / "chunks").resolve()
BATCH_SIZE  = 200
REFRESH_INTERVAL = "30s"

if not ES_URL:
    sys.exit("ELASTICSEARCH_URL is not set in .env")
if not ES_API_KEY:
    sys.exit("ELASTICSEARCH_API_KEY is not set in .env")
if not CHUNKS_DIR.is_dir():
    sys.exit(f"Chunks directory not found: {CHUNKS_DIR}")


# =============================================================================
# INDEX MAPPING  (mirrors app/elasticsearch/mapping.py)
# =============================================================================

INDEX_BODY: Dict[str, Any] = {
    "settings": {
        # Note: number_of_shards / number_of_replicas / refresh_interval are
        # NOT supported in Elasticsearch serverless mode (v9+).
        "analysis": {
            "filter": {
                "legal_stop": {
                    "type": "stop",
                    "stopwords": "_english_",
                },
                "legal_stemmer": {
                    "type": "stemmer",
                    "language": "english",
                },
                "legal_word_delimiter": {
                    "type": "word_delimiter_graph",
                    "preserve_original": True,
                    "catenate_words": True,
                    "catenate_numbers": True,
                    "split_on_case_change": False,
                },
            },
            "analyzer": {
                "legal_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "legal_word_delimiter",
                        "legal_stop",
                        "legal_stemmer",
                    ],
                }
            },
        },
    },
    "mappings": {
        "properties": {
            "chunk_id":      {"type": "keyword"},
            "document_id":   {"type": "keyword"},
            "document_name": {
                "type": "text",
                "analyzer": "legal_analyzer",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "category":      {"type": "keyword"},
            "page_number":   {"type": "integer"},
            "chunk_index":   {"type": "integer"},
            "chunk_text": {
                "type": "text",
                "analyzer": "legal_analyzer",
                "fields": {"exact": {"type": "text", "analyzer": "standard"}},
            },
            "source":       {"type": "keyword"},
            "indexed_at":   {"type": "date"},
            "metadata":     {"type": "object", "dynamic": True},
        }
    },
}


# =============================================================================
# HELPERS
# =============================================================================

def build_client() -> Elasticsearch:
    """Build and return a configured Elasticsearch client."""
    return Elasticsearch(
        hosts=[ES_URL],
        api_key=ES_API_KEY,
        request_timeout=60,
        retry_on_timeout=True,
        max_retries=3,
    )


def ensure_index(client: Elasticsearch) -> None:
    """Create the index if it does not exist, using the full legal mapping."""
    if client.indices.exists(index=INDEX_NAME):
        print(f"Index '{INDEX_NAME}' already exists -- skipping creation.")
        return
    client.indices.create(index=INDEX_NAME, body=INDEX_BODY)
    print(f"Index '{INDEX_NAME}' created with legal_analyzer mapping.")


def load_all_chunks(chunks_dir: Path) -> List[Dict[str, Any]]:
    """
    Read all *_chunks.json files and return a flat list of chunk dicts.

    The JSON files contain a top-level dict with a "chunks" array.  Each
    chunk dict has at minimum:
        chunk_id, document_id, document_name, category,
        page (or page_number), chunk_index, text, metadata
    """
    all_chunks: List[Dict[str, Any]] = []
    chunk_files = sorted(chunks_dir.glob("*_chunks.json"))
    print(f"\nFound {len(chunk_files)} chunk files in {chunks_dir}")

    for chunk_file in chunk_files:
        try:
            data = json.loads(chunk_file.read_text(encoding="utf-8"))
            # The file is either a list or a dict with a "chunks" key
            if isinstance(data, list):
                chunks = data
            elif isinstance(data, dict):
                chunks = data.get("chunks", [])
            else:
                print(f"  WARNING: Unexpected format in {chunk_file.name} -- skipping")
                continue
            all_chunks.extend(chunks)
        except Exception as exc:
            print(f"  WARNING: Failed to read {chunk_file.name}: {exc}")

    print(f"Total chunks loaded: {len(all_chunks):,}")
    return all_chunks


def chunk_to_action(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a raw chunk dict to an Elasticsearch bulk-index action.

    Handles both 'page' and 'page_number' field names that appear in
    different versions of the chunk files.
    """
    # Normalise page number field
    page_number = (
        chunk.get("page_number")
        or chunk.get("page")
        or chunk.get("metadata", {}).get("page_number")
        or 0
    )

    # Clean text
    raw_text = chunk.get("text", "") or ""
    clean_text = re.sub(r"\s+", " ", raw_text).strip()

    # Preserve all metadata fields
    metadata = dict(chunk.get("metadata", {}))
    # Enrich metadata with any extra fields not already present
    for extra_key in ("file_path", "source", "chunk_size", "char_count", "token_estimate"):
        if extra_key in chunk and extra_key not in metadata:
            metadata[extra_key] = chunk[extra_key]

    return {
        "_index": INDEX_NAME,
        "_id":    chunk["chunk_id"],  # idempotent upsert
        "_source": {
            "chunk_id":      chunk["chunk_id"],
            "document_id":   chunk["document_id"],
            "document_name": chunk.get("document_name", ""),
            "category":      chunk.get("category", "Other"),
            "page_number":   int(page_number),
            "chunk_index":   chunk.get("chunk_index", 0),
            "chunk_text":    clean_text,
            "source":        "keyword",
            "indexed_at":    datetime.now(timezone.utc).isoformat(),
            "metadata":      metadata,
        },
    }


def bulk_index(
    client: Elasticsearch,
    chunks: List[Dict[str, Any]],
    batch_size: int = BATCH_SIZE,
) -> Tuple[int, int]:
    """Bulk-index chunks in batches; returns (success_count, error_count)."""
    total_success = 0
    total_errors  = 0
    batches = [chunks[i: i + batch_size] for i in range(0, len(chunks), batch_size)]
    num_batches = len(batches)
    start = time.perf_counter()

    print(f"\nIndexing {len(chunks):,} chunks in {num_batches} batches (size={batch_size})...\n")

    for batch_num, batch in enumerate(batches, start=1):
        # Filter out chunks with empty text before building actions
        valid = [c for c in batch if (c.get("text") or "").strip()]
        skipped = len(batch) - len(valid)

        if not valid:
            print(f"  Batch {batch_num:>4}/{num_batches} -- all chunks empty, skipped")
            continue

        actions = [chunk_to_action(c) for c in valid]

        try:
            t0 = time.perf_counter()
            success, errors = es_bulk(client, actions, raise_on_error=False, stats_only=False)
            elapsed = (time.perf_counter() - t0) * 1000

            total_success += success
            err_count = len(errors) if isinstance(errors, list) else 0
            total_errors += err_count

            status_icon = "OK" if err_count == 0 else "WARN"
            print(
                f"  [{status_icon}] Batch {batch_num:>4}/{num_batches} | "
                f"indexed={success:>5} | errors={err_count} | "
                f"skipped={skipped} | {elapsed:.0f}ms"
            )
        except Exception as exc:
            total_errors += len(valid)
            print(f"  [FAIL] Batch {batch_num}/{num_batches}: {exc}")

    wall = time.perf_counter() - start
    print(f"\nBulk indexing complete in {wall:.1f}s")
    return total_success, total_errors


def verify_index(client: Elasticsearch) -> None:
    """Refresh the index and run a sample BM25 search to confirm it works."""
    print("\nRefreshing index...")
    client.indices.refresh(index=INDEX_NAME)

    # Doc count
    count_resp = client.count(index=INDEX_NAME)
    total_docs = count_resp["count"]
    print(f"Total documents in index: {total_docs:,}")

    # Index health
    health = client.cluster.health(index=INDEX_NAME)
    print(f"Index health: {health.get('status', 'unknown').upper()}")

    # Sample BM25 search
    print("\nSample BM25 query: 'tax deduction qualified business income'")
    resp = client.search(
        index=INDEX_NAME,
        body={
            "query": {
                "match": {
                    "chunk_text": {
                        "query": "tax deduction qualified business income",
                        "operator": "or",
                    }
                }
            },
            "size": 3,
            "_source": ["chunk_id", "document_name", "category", "page_number", "chunk_text"],
        },
    )
    hits = resp["hits"]["hits"]
    total_hits = resp["hits"]["total"]["value"]
    print(f"  Total hits: {total_hits:,}")
    for i, hit in enumerate(hits, start=1):
        src = hit["_source"]
        snippet = src.get("chunk_text", "")[:120].replace("\n", " ")
        print(
            f"  [{i}] {src.get('document_name')} | "
            f"p.{src.get('page_number')} | "
            f"cat={src.get('category')} | "
            f"score={hit['_score']:.3f}"
        )
        print(f"       \"{snippet}...\"")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    print("=" * 70)
    print("  Legal-AI-Assistant -- Elasticsearch Bulk Re-indexing Script")
    print("=" * 70)
    print(f"  Cluster : {ES_URL}")
    print(f"  Index   : {INDEX_NAME}")
    print(f"  Chunks  : {CHUNKS_DIR}")
    print("=" * 70)

    # Step 1: Connect
    print("\nConnecting to Elasticsearch...")
    client = build_client()
    if not client.ping():
        sys.exit("Cannot reach Elasticsearch -- check URL and API key.")
    info = client.info()
    print(f"Connected | cluster={info['cluster_name']} | version={info['version']['number']}")

    # Step 2: Ensure index
    print(f"\nChecking index '{INDEX_NAME}'...")
    ensure_index(client)

    # Step 3: Load chunks
    all_chunks = load_all_chunks(CHUNKS_DIR)
    if not all_chunks:
        sys.exit("No chunks found -- check that metadata/chunks/ has *_chunks.json files.")

    # Step 4: Bulk index
    success, errors = bulk_index(client, all_chunks)

    # Step 5: Verify
    verify_index(client)

    # Summary
    print("\n" + "=" * 70)
    print("  INDEXING COMPLETE")
    print(f"  Successfully indexed : {success:,}")
    print(f"  Failed               : {errors:,}")
    if errors == 0:
        print("\n  Hybrid Search is READY -- BM25 + Vector search fully operational!")
    else:
        print(f"\n  WARNING: {errors} chunks failed. Check logs above for details.")
    print("=" * 70)


if __name__ == "__main__":
    main()
