"""
app/golden_set/statistics.py
==============================
Statistics engine for the Golden Set Management Module.

PURPOSE:
    Computes aggregate statistics from a list of GoldenRecord objects.
    Used after validation to produce the dashboard metrics displayed in
    the frontend Statistics Dashboard.

STATISTICS COMPUTED:
    - Total / Valid / Invalid / Duplicate / Rejected query counts
    - Category distribution (valid records per category)
    - Per-category breakdown (CategoryStats with avg query length)
    - Average query length across valid records
    - Average expected answer length across valid records
    - Count of unique source documents (valid records)

DESIGN:
    - Stateless: single public method compute()
    - Pure computation — no I/O, no logging side-effects
    - Returns GoldenSetStatistics domain model

SOLID: Single Responsibility — statistics computation only.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

from app.golden_set.golden_models import (
    CategoryStats,
    GoldenRecord,
    GoldenRecordStatus,
    GoldenSetStatistics,
)


class StatisticsEngine:
    """
    Computes aggregate statistics from a list of GoldenRecord objects.

    Usage:
        engine = StatisticsEngine()
        stats = engine.compute(records, source_file="golden_set.csv")
    """

    def compute(
        self,
        records: List[GoldenRecord],
        source_file: str = "unknown",
    ) -> GoldenSetStatistics:
        """
        Compute all golden set statistics from the provided records list.

        Args:
            records:     All GoldenRecord objects (all statuses).
            source_file: Name of the source file that was imported.

        Returns:
            GoldenSetStatistics with all computed metrics.
        """
        # ── Count records by status ───────────────────────────────────────────
        total_queries = len(records)
        valid_queries = sum(1 for r in records if r.status == GoldenRecordStatus.VALID)
        invalid_queries = sum(1 for r in records if r.status == GoldenRecordStatus.INVALID)
        duplicate_queries = sum(1 for r in records if r.status == GoldenRecordStatus.DUPLICATE)
        rejected_queries = sum(1 for r in records if r.status == GoldenRecordStatus.REJECTED)

        # ── Filter valid records for metric computation ───────────────────────
        valid_records = [r for r in records if r.status == GoldenRecordStatus.VALID]

        # ── Category distribution (valid only) ───────────────────────────────
        category_distribution: Dict[str, int] = {}
        for record in valid_records:
            cat = record.category or "Unknown"
            category_distribution[cat] = category_distribution.get(cat, 0) + 1

        # ── Per-category stats (all statuses) ─────────────────────────────────
        cat_total: Dict[str, int] = defaultdict(int)
        cat_valid: Dict[str, int] = defaultdict(int)
        cat_invalid: Dict[str, int] = defaultdict(int)
        cat_duplicate: Dict[str, int] = defaultdict(int)
        cat_query_lengths: Dict[str, List[int]] = defaultdict(list)

        for record in records:
            if record.status == GoldenRecordStatus.REJECTED:
                continue  # Rejected rows have no meaningful category
            cat = record.category or "Unknown"
            cat_total[cat] += 1
            if record.status == GoldenRecordStatus.VALID:
                cat_valid[cat] += 1
                cat_query_lengths[cat].append(record.query_length)
            elif record.status == GoldenRecordStatus.INVALID:
                cat_invalid[cat] += 1
            elif record.status == GoldenRecordStatus.DUPLICATE:
                cat_duplicate[cat] += 1

        category_stats: List[CategoryStats] = []
        all_cats = sorted(set(
            list(cat_total.keys()) + list(category_distribution.keys())
        ))
        for cat in all_cats:
            lengths = cat_query_lengths.get(cat, [])
            avg_len = sum(lengths) / len(lengths) if lengths else 0.0
            category_stats.append(CategoryStats(
                category=cat,
                total=cat_total.get(cat, 0),
                valid=cat_valid.get(cat, 0),
                invalid=cat_invalid.get(cat, 0),
                duplicate=cat_duplicate.get(cat, 0),
                avg_query_len=avg_len,
            ))

        # ── Average query length (valid records only) ─────────────────────────
        if valid_records:
            avg_query_length = sum(r.query_length for r in valid_records) / len(valid_records)
            avg_answer_length = sum(r.answer_length for r in valid_records) / len(valid_records)
        else:
            avg_query_length = 0.0
            avg_answer_length = 0.0

        # ── Unique source documents (valid only) ──────────────────────────────
        unique_source_docs = len({r.source_document for r in valid_records if r.source_document})

        return GoldenSetStatistics(
            total_queries=total_queries,
            valid_queries=valid_queries,
            invalid_queries=invalid_queries,
            duplicate_queries=duplicate_queries,
            rejected_queries=rejected_queries,
            category_distribution=category_distribution,
            category_stats=category_stats,
            avg_query_length=avg_query_length,
            avg_answer_length=avg_answer_length,
            unique_source_docs=unique_source_docs,
            computed_at=datetime.now(timezone.utc),
            source_file=source_file,
        )
