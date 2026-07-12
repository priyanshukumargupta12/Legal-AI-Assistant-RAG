"""
app/golden_set/csv_importer.py
================================
CSV file importer for the Golden Set Management Module.

PURPOSE:
    Reads a golden set CSV file and returns a list of raw row dictionaries
    with canonical column names. Handles multiple encodings automatically
    (UTF-8, UTF-16, latin-1 fallback) and normalizes column headers using
    the alias mapping system in golden_utils.

    This class performs NO validation — it only handles I/O and column mapping.
    Validation is the responsibility of GoldenSetValidator.

DESIGN:
    - Single public method: import_file(path) → List[Dict]
    - Returns raw dict rows with canonical column names
    - Raises GoldenSetImportError on unrecoverable read failures
    - Strips BOM (Byte Order Mark) from UTF-8 files automatically

SOLID: Single Responsibility — CSV reading and column normalization only.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

from app.core.exceptions import GoldenSetImportError
from app.golden_set.golden_logger import golden_log
from app.golden_set.golden_utils import (
    build_column_mapping,
    detect_encoding,
    sanitize_text,
)


class CSVImporter:
    """
    Reads a golden set CSV file into a list of raw row dictionaries.

    Each row dict uses canonical column names (e.g., "expected_answer"
    instead of "Ground_Truth_Answer").

    Usage:
        importer = CSVImporter()
        rows = importer.import_file(Path("metadata/golden_set.csv"))
    """

    # Encoding fallback chain for CSV files
    _ENCODING_FALLBACKS: tuple[str, ...] = ("utf-8-sig", "utf-16", "latin-1", "cp1252")

    def import_file(self, file_path: Path) -> List[Dict[str, Optional[str]]]:
        """
        Read a CSV file and return all rows with canonical column names.

        Performs automatic encoding detection. On BOM-present UTF-8 files
        (utf-8-sig), the BOM is stripped automatically by Python's csv module.

        Args:
            file_path: Absolute path to the CSV file.

        Returns:
            List of dicts mapping canonical column names → raw string values.
            Empty list if the file has no data rows.

        Raises:
            GoldenSetImportError: If the file cannot be read or has no header.
        """
        golden_log.info(
            "CSV import started | file={file} | size={size} bytes",
            file=file_path.name,
            size=file_path.stat().st_size if file_path.exists() else -1,
        )

        if not file_path.exists():
            raise GoldenSetImportError(
                message=f"Golden set CSV file not found: {file_path}",
            )

        if file_path.stat().st_size == 0:
            raise GoldenSetImportError(
                message=f"Golden set CSV file is empty: {file_path.name}",
            )

        # 1. Detect encoding
        encoding = detect_encoding(file_path)

        # 2. Try primary detected encoding, then fallback chain
        rows: List[Dict[str, Optional[str]]] = []
        encodings_to_try = [encoding] + [
            e for e in self._ENCODING_FALLBACKS if e != encoding
        ]

        last_error: Optional[Exception] = None
        for enc in encodings_to_try:
            try:
                rows = self._read_csv(file_path, enc)
                golden_log.info(
                    "CSV read successful | file={file} | encoding={enc} | rows={count}",
                    file=file_path.name,
                    enc=enc,
                    count=len(rows),
                )
                break
            except (UnicodeDecodeError, UnicodeError) as exc:
                golden_log.warning(
                    "Encoding {enc} failed for {file}: {err}; trying next",
                    enc=enc,
                    file=file_path.name,
                    err=str(exc),
                )
                last_error = exc
                continue
            except GoldenSetImportError:
                raise
            except Exception as exc:
                last_error = exc
                break

        if not rows and last_error:
            raise GoldenSetImportError(
                message=f"Failed to read CSV file '{file_path.name}' with any encoding: {last_error}",
            )

        golden_log.info(
            "CSV import finished | file={file} | rows={count}",
            file=file_path.name,
            count=len(rows),
        )
        return rows

    def _read_csv(
        self, file_path: Path, encoding: str
    ) -> List[Dict[str, Optional[str]]]:
        """
        Internal: Read CSV with a specific encoding and normalize column names.

        Args:
            file_path: Path to the CSV file.
            encoding:  Encoding to use when opening the file.

        Returns:
            List of dicts with canonical column names.

        Raises:
            GoldenSetImportError: If the CSV has no header row.
            UnicodeDecodeError:   If the encoding is incorrect.
        """
        with open(file_path, "r", encoding=encoding, newline="") as csvfile:
            # Use Sniffer to auto-detect dialect (comma vs semicolon vs tab)
            sample = csvfile.read(4096)
            csvfile.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel  # type: ignore[assignment]

            reader = csv.DictReader(csvfile, dialect=dialect)

            # Validate header exists
            if reader.fieldnames is None or len(reader.fieldnames) == 0:
                raise GoldenSetImportError(
                    message=f"CSV file '{file_path.name}' has no header row.",
                )

            # Build column mapping (raw header → canonical name)
            column_map = build_column_mapping(list(reader.fieldnames))
            golden_log.debug(
                "Column mapping: {mapping}",
                mapping=column_map,
            )

            rows: List[Dict[str, Optional[str]]] = []
            for raw_row in reader:
                # Remap column names to canonical form
                mapped_row: Dict[str, Optional[str]] = {}
                for raw_col, canonical_col in column_map.items():
                    raw_val = raw_row.get(raw_col)
                    mapped_row[canonical_col] = sanitize_text(raw_val)
                rows.append(mapped_row)

        return rows
