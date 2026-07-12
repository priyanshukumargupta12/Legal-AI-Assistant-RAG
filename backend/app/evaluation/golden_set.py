"""
evaluation/golden_set.py
=========================
Golden set CSV/Excel importer and validator.

PURPOSE:
    Reads golden_set.csv or golden_set.xlsx, validates required columns,
    and returns a list of validated GoldenSetEntry objects.

SOLID: Single Responsibility — golden set import and validation only.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

from app.core.exceptions import GoldenSetImportError
from app.golden_set.golden_utils import build_column_mapping, sanitize_page_number, sanitize_text


@dataclass(frozen=True)
class GoldenSetEntry:
    """
    A single query-answer evaluation benchmark entry.
    """
    query: str
    expected_answer: str
    source_document: str
    page_number: int
    category: str


class GoldenSetImporter:
    """
    Importer and validator for golden set files.
    """

    @classmethod
    def import_csv(cls, file_path: str | Path) -> List[GoldenSetEntry]:
        """
        Import CSV golden set file and return list of GoldenSetEntry.
        """
        path = Path(file_path)
        if not path.exists():
            raise GoldenSetImportError(f"Golden set file not found: {path}")

        entries: List[GoldenSetEntry] = []
        try:
            # Detect encoding and read headers
            with open(path, "r", encoding="utf-8-sig", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                if not reader.fieldnames:
                    raise GoldenSetImportError("CSV file has no header row.")
                
                # Standardize headers
                column_map = build_column_mapping(list(reader.fieldnames))
                
                for row in reader:
                    # Map raw keys to canonical keys
                    mapped_row = {column_map.get(k, k): v for k, v in row.items()}
                    entry = cls._parse_row_dict(mapped_row)
                    if entry:
                        entries.append(entry)
        except Exception as exc:
            raise GoldenSetImportError(f"Failed to read CSV golden set: {exc}")

        return entries

    @classmethod
    def import_excel(cls, file_path: str | Path) -> List[GoldenSetEntry]:
        """
        Import Excel golden set file and return list of GoldenSetEntry.
        """
        path = Path(file_path)
        if not path.exists():
            raise GoldenSetImportError(f"Golden set file not found: {path}")

        entries: List[GoldenSetEntry] = []
        try:
            # Read via pandas
            df = pd.read_excel(path)
            # Standardize headers
            column_map = build_column_mapping(list(df.columns))
            df = df.rename(columns=column_map)
            
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                entry = cls._parse_row_dict(row_dict)
                if entry:
                    entries.append(entry)
        except Exception as exc:
            raise GoldenSetImportError(f"Failed to read Excel golden set: {exc}")

        return entries

    @classmethod
    def _parse_row_dict(cls, row: Dict[str, Any]) -> Optional[GoldenSetEntry]:
        """
        Parses a row dictionary into a GoldenSetEntry.
        """
        query = sanitize_text(row.get("query"))
        expected_answer = sanitize_text(row.get("expected_answer"))
        source_document = sanitize_text(row.get("source_document"))
        page_num = sanitize_page_number(row.get("page_number"))
        category = sanitize_text(row.get("category"))

        # Skip empty rows or rows missing critical columns
        if not query or not expected_answer or not source_document or page_num is None or not category:
            return None

        return GoldenSetEntry(
            query=query,
            expected_answer=expected_answer,
            source_document=source_document,
            page_number=page_num,
            category=category,
        )
