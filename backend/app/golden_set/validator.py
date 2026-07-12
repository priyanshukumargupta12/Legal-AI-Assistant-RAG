"""
app/golden_set/validator.py
============================
Golden Set record validator for the Golden Set Management Module.

PURPOSE:
    Validates every raw row dict produced by CSVImporter or ExcelImporter
    against all required business rules. Produces:
        - A list of valid GoldenRecord objects
        - A complete ValidationReport with all errors found

VALIDATION RULES:
    1. EMPTY_ROW         — Skip completely empty rows (all fields None/empty)
    2. MISSING_QUERY     — Query field is None or empty string
    3. MISSING_ANSWER    — Expected Answer field is None or empty string
    4. MISSING_SOURCE    — Source Document field is None or empty string
    5. INVALID_PAGE      — Page Number cannot be parsed as a positive integer
    6. UNKNOWN_CATEGORY  — Category is not in VALID_CATEGORIES
    7. DUPLICATE_QUERY   — Another record already has the same query (case-insensitive)

DESIGN:
    - Stateless: no instance fields mutated between calls
    - Single public method: validate_records()
    - Returns (records, report) — caller decides what to do with each
    - Does NOT raise exceptions — validation errors are returned in the report

SOLID: Single Responsibility — record-level validation logic only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from app.core.constants import VALID_CATEGORIES
from app.golden_set.golden_logger import golden_log
from app.golden_set.golden_models import (
    FieldValidationError,
    GoldenRecord,
    GoldenRecordStatus,
    ValidationReport,
)
from app.golden_set.golden_utils import sanitize_page_number, sanitize_text


class GoldenSetValidator:
    """
    Validates raw row dicts against all golden set business rules.

    Each row dict must use canonical column names (produced by
    CSVImporter or ExcelImporter). Validation is performed in a single
    pass over all rows for efficiency.

    Usage:
        validator = GoldenSetValidator()
        records, report = validator.validate_records(rows, source_file="golden_set.csv")
    """

    # Required canonical fields
    _REQUIRED_FIELDS: Tuple[str, ...] = (
        "query",
        "expected_answer",
        "source_document",
        "page_number",
        "category",
    )

    # Optional canonical fields
    _OPTIONAL_FIELDS: Tuple[str, ...] = (
        "citation",
        "difficulty",
        "tags",
        "notes",
    )

    def validate_records(
        self,
        rows: List[Dict],
        source_file: str = "unknown",
    ) -> Tuple[List[GoldenRecord], ValidationReport]:
        """
        Validate all rows and produce a list of GoldenRecords + ValidationReport.

        Processing order per row:
            1. Detect and skip empty rows (REJECTED)
            2. Check required fields (MISSING_*)
            3. Validate page number (INVALID_PAGE)
            4. Validate category (UNKNOWN_CATEGORY)
            5. Check for duplicate queries (DUPLICATE_QUERY)
            6. If no errors → mark VALID

        Args:
            rows:        List of raw row dicts with canonical column names.
            source_file: Filename string used in the ValidationReport.

        Returns:
            Tuple of (list of GoldenRecord, ValidationReport).
        """
        golden_log.info(
            "Validation started | source={file} | rows={count}",
            file=source_file,
            count=len(rows),
        )

        records: List[GoldenRecord] = []
        all_errors: List[FieldValidationError] = []
        seen_queries: Set[str] = set()  # lowercase normalized queries for dedup

        valid_count = 0
        invalid_count = 0
        duplicate_count = 0
        rejected_count = 0

        for i, row in enumerate(rows, start=2):  # start=2: row 1 = header
            row_errors: List[FieldValidationError] = []

            # ── Step 1: Detect empty row ──────────────────────────────────────
            if self._is_empty_row(row):
                rejected_count += 1
                golden_log.debug("Row {row}: empty row — rejected", row=i)
                # Still create a placeholder rejected record
                records.append(GoldenRecord(
                    query="",
                    expected_answer="",
                    source_document="",
                    page_number=0,
                    category="",
                    row_number=i,
                    status=GoldenRecordStatus.REJECTED,
                ))
                continue

            # ── Step 2: Extract and validate required fields ──────────────────
            query = sanitize_text(row.get("query"))
            expected_answer = sanitize_text(row.get("expected_answer"))
            source_document = sanitize_text(row.get("source_document"))
            raw_page = row.get("page_number")
            category = sanitize_text(row.get("category"))

            # MISSING_QUERY
            if not query:
                row_errors.append(FieldValidationError(
                    row_number=i,
                    field_name="query",
                    error_code="MISSING_QUERY",
                    error_message="Query field is missing or empty.",
                    raw_value=str(row.get("query", "")),
                ))

            # MISSING_ANSWER
            if not expected_answer:
                row_errors.append(FieldValidationError(
                    row_number=i,
                    field_name="expected_answer",
                    error_code="MISSING_ANSWER",
                    error_message="Expected Answer field is missing or empty.",
                    raw_value=str(row.get("expected_answer", "")),
                ))

            # MISSING_SOURCE
            if not source_document:
                row_errors.append(FieldValidationError(
                    row_number=i,
                    field_name="source_document",
                    error_code="MISSING_SOURCE",
                    error_message="Source Document field is missing or empty.",
                    raw_value=str(row.get("source_document", "")),
                ))

            # ── Step 3: Validate page number ──────────────────────────────────
            page_number = sanitize_page_number(raw_page)
            if page_number is None:
                row_errors.append(FieldValidationError(
                    row_number=i,
                    field_name="page_number",
                    error_code="INVALID_PAGE",
                    error_message=(
                        "Page Number must be a positive integer. "
                        f"Got: {str(raw_page)!r}"
                    ),
                    raw_value=str(raw_page) if raw_page is not None else None,
                ))
                page_number = 0  # Use 0 as safe default for invalid records

            # ── Step 4: Validate category ─────────────────────────────────────
            if category and category not in VALID_CATEGORIES:
                row_errors.append(FieldValidationError(
                    row_number=i,
                    field_name="category",
                    error_code="UNKNOWN_CATEGORY",
                    error_message=(
                        f"Category '{category}' is not valid. "
                        f"Must be one of: {', '.join(VALID_CATEGORIES)}"
                    ),
                    raw_value=category,
                ))
            elif not category:
                row_errors.append(FieldValidationError(
                    row_number=i,
                    field_name="category",
                    error_code="MISSING_CATEGORY",
                    error_message="Category field is missing or empty.",
                    raw_value=str(row.get("category", "")),
                ))

            # ── Step 5: Duplicate query check ─────────────────────────────────
            # Only check if query exists (missing query already errors above)
            is_duplicate = False
            if query:
                query_key = query.strip().lower()
                if query_key in seen_queries:
                    is_duplicate = True
                    row_errors.append(FieldValidationError(
                        row_number=i,
                        field_name="query",
                        error_code="DUPLICATE_QUERY",
                        error_message=f"Duplicate query detected (case-insensitive match).",
                        raw_value=query[:100],
                    ))
                else:
                    seen_queries.add(query_key)

            # ── Step 6: Build GoldenRecord ─────────────────────────────────────
            # Determine status
            if is_duplicate and not [e for e in row_errors if e.error_code != "DUPLICATE_QUERY"]:
                status = GoldenRecordStatus.DUPLICATE
                duplicate_count += 1
            elif row_errors:
                status = GoldenRecordStatus.INVALID
                invalid_count += 1
            else:
                status = GoldenRecordStatus.VALID
                valid_count += 1

            record = GoldenRecord(
                query=query or "",
                expected_answer=expected_answer or "",
                source_document=source_document or "",
                page_number=page_number,
                category=category or "",
                citation=sanitize_text(row.get("citation")),
                difficulty=sanitize_text(row.get("difficulty")),
                tags=sanitize_text(row.get("tags")),
                notes=sanitize_text(row.get("notes")),
                row_number=i,
                status=status,
                is_duplicate_of=query if is_duplicate else None,
                validation_errors=row_errors,
            )
            records.append(record)
            all_errors.extend(row_errors)

        # ── Build ValidationReport ────────────────────────────────────────────
        report = ValidationReport(
            total_rows=len(rows),
            valid_count=valid_count,
            invalid_count=invalid_count,
            duplicate_count=duplicate_count,
            rejected_count=rejected_count,
            errors=all_errors,
            validated_at=datetime.now(timezone.utc),
            source_file=source_file,
        )

        golden_log.info(
            "Validation complete | valid={v} | invalid={i} | duplicate={d} | rejected={r} | errors={e}",
            v=valid_count,
            i=invalid_count,
            d=duplicate_count,
            r=rejected_count,
            e=len(all_errors),
        )

        return records, report

    @staticmethod
    def _is_empty_row(row: Dict) -> bool:
        """
        Return True if all values in the row are None or empty strings.

        Args:
            row: Raw row dict with canonical column names.

        Returns:
            True if the row is completely empty; False otherwise.
        """
        return all(
            v is None or str(v).strip() == ""
            for v in row.values()
        )
