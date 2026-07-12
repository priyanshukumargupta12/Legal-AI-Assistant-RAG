"""
app/elasticsearch/bulk_index.py
=================================
Elasticsearch bulk indexing helper.

PURPOSE:
    Wraps the ``elasticsearch.helpers.bulk`` utility to provide batched,
    error-tolerant bulk indexing of ``ElasticsearchDocument`` objects.
    Separates the bulk mechanics from the service layer so they can be
    tested and replaced independently.

DESIGN:
    - Uses ``elasticsearch.helpers.bulk`` for high-throughput ingestion.
    - Splits documents into configurable batch sizes to control memory usage.
    - Captures per-item errors without aborting the entire batch.
    - Returns (success_count, error_count, error_list).

SOLID:
    Single Responsibility — only manages bulk indexing mechanics.
    Open/Closed — extend by subclassing or passing a different action builder.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, BulkIndexError

from app.elasticsearch.elastic_logger import elastic_log
from app.elasticsearch.elastic_models import ElasticsearchDocument
from app.elasticsearch.elastic_utils import build_bulk_actions


def bulk_index_documents(
    client: Elasticsearch,
    documents: List[ElasticsearchDocument],
    index_name: str,
    batch_size: int = 200,
    raise_on_error: bool = False,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Bulk-index a list of ``ElasticsearchDocument`` objects into Elasticsearch.

    Documents are split into batches of ``batch_size`` to avoid overwhelming
    the Elasticsearch cluster or exhausting local memory.

    Args:
        client:         Configured ``Elasticsearch`` client instance.
        documents:      Documents to index.
        index_name:     Target index name.
        batch_size:     Maximum documents per bulk request (default: 200).
        raise_on_error: If True, re-raises ``BulkIndexError`` on failure.
                        If False, errors are collected and returned.

    Returns:
        Tuple of:
            success_count: Total documents successfully indexed.
            error_count:   Total documents that failed.
            errors:        List of error dicts from failed operations.
    """
    if not documents:
        elastic_log.info("No documents to bulk-index.")
        return 0, 0, []

    total_success = 0
    total_errors = 0
    all_errors: List[Dict[str, Any]] = []

    # ── Split into batches ─────────────────────────────────────────────────────
    batches = [
        documents[i : i + batch_size]
        for i in range(0, len(documents), batch_size)
    ]
    num_batches = len(batches)

    elastic_log.info(
        "Starting bulk indexing | total_docs={total} | batches={batches} | batch_size={bs}",
        total=len(documents),
        batches=num_batches,
        bs=batch_size,
    )

    for batch_num, batch_docs in enumerate(batches, start=1):
        t0 = time.perf_counter()
        actions = build_bulk_actions(batch_docs, index_name=index_name)

        try:
            success, errors = bulk(
                client,
                actions,
                raise_on_error=False,  # collect errors instead of raising
                stats_only=False,
            )
            elapsed = time.perf_counter() - t0
            total_success += success
            if errors:
                total_errors += len(errors)
                all_errors.extend(errors)
                elastic_log.warning(
                    "Batch {batch}/{total} completed with errors | success={s} | errors={e} | time={t:.2f}s",
                    batch=batch_num,
                    total=num_batches,
                    s=success,
                    e=len(errors),
                    t=elapsed,
                )
            else:
                elastic_log.info(
                    "Batch {batch}/{total} indexed successfully | docs={docs} | time={t:.2f}s",
                    batch=batch_num,
                    total=num_batches,
                    docs=success,
                    t=elapsed,
                )

        except BulkIndexError as exc:
            elapsed = time.perf_counter() - t0
            elastic_log.error(
                "BulkIndexError on batch {batch}/{total} | errors={e} | time={t:.2f}s",
                batch=batch_num,
                total=num_batches,
                e=len(exc.errors),
                t=elapsed,
            )
            total_errors += len(exc.errors)
            all_errors.extend(exc.errors)
            if raise_on_error:
                raise

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            elastic_log.error(
                "Unexpected error on batch {batch}/{total} | error={err} | time={t:.2f}s",
                batch=batch_num,
                total=num_batches,
                err=str(exc),
                t=elapsed,
            )
            total_errors += len(batch_docs)
            if raise_on_error:
                raise

    elastic_log.info(
        "Bulk indexing complete | indexed={s} | failed={e}",
        s=total_success,
        e=total_errors,
    )
    return total_success, total_errors, all_errors
