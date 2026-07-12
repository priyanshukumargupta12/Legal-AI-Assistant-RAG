"""
app/golden_set/excel_importer.py
==================================
Excel (.xlsx) file importer for the Golden Set Management Module.

PURPOSE:
    Reads a golden set Excel (.xlsx) file using openpyxl and returns a
    list of raw row dictionaries with canonical column names. Handles
    merged cells, empty rows, and flexible column header positions.

    This class performs NO validation — it only handles I/O and column mapping.
    Validation is the responsibility of GoldenSetValidator.

DESIGN:
    - Single public method: import_file(path) → List[Dict]
    - Reads only the first (active) worksheet
    - Strips merged-cell artifacts
    - Raises GoldenSetImportError on unrecoverable read failures

SOLID: Single Responsibility — XLSX reading and column normalization only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.exceptions import GoldenSetImportError
from app.golden_set.golden_logger import golden_log
from app.golden_set.golden_utils import (
    build_column_mapping,
    sanitize_text,
)


class ExcelImporter:
    """
    Reads a golden set .xlsx file into a list of raw row dictionaries.

    Each row dict uses canonical column names (e.g., "expected_answer"
    instead of "Ground_Truth_Answer") via the shared alias mapping system.

    Usage:
        importer = ExcelImporter()
        rows = importer.import_file(Path("metadata/golden_set.xlsx"))
    """

    def import_file(self, file_path: Path) -> List[Dict[str, Optional[str]]]:
        """
        Read an Excel (.xlsx) file and return all rows with canonical column names.

        Reads only the active (first) worksheet. Skips rows where all
        cells are empty. Handles merged cells by treating them as None.

        Args:
            file_path: Absolute path to the .xlsx file.

        Returns:
            List of dicts mapping canonical column names → raw string values.
            Empty list if the worksheet has no data rows.

        Raises:
            GoldenSetImportError: If the file cannot be read, is not xlsx, or has no header.
        """
        golden_log.info(
            "Excel import started | file={file} | size={size} bytes",
            file=file_path.name,
            size=file_path.stat().st_size if file_path.exists() else -1,
        )

        if not file_path.exists():
            raise GoldenSetImportError(
                message=f"Golden set Excel file not found: {file_path}",
            )

        if file_path.stat().st_size == 0:
            raise GoldenSetImportError(
                message=f"Golden set Excel file is empty: {file_path.name}",
            )

        try:
            import openpyxl  # type: ignore
        except ImportError as exc:
            raise GoldenSetImportError(
                message="openpyxl is required to read .xlsx files. Install it with: pip install openpyxl",
            ) from exc

        try:
            # data_only=True reads computed cell values rather than formulas
            wb = openpyxl.load_workbook(str(file_path), data_only=True, read_only=True)
        except Exception as exc:
            raise GoldenSetImportError(
                message=f"Failed to open Excel file '{file_path.name}': {exc}",
            ) from exc

        try:
            ws = wb.active
            if ws is None:
                raise GoldenSetImportError(
                    message=f"Excel file '{file_path.name}' has no active worksheet.",
                )

            rows = self._extract_rows(ws, file_path.name)
        finally:
            wb.close()

        golden_log.info(
            "Excel import finished | file={file} | rows={count}",
            file=file_path.name,
            count=len(rows),
        )
        return rows

    def _extract_rows(
        self, worksheet: Any, file_name: str
    ) -> List[Dict[str, Optional[str]]]:
        """
        Extract all data rows from an openpyxl worksheet.

        The first non-empty row is treated as the header row.
        All subsequent rows are mapped using the canonical column mapping.

        Args:
            worksheet: An openpyxl Worksheet object.
            file_name: Filename for error messages.

        Returns:
            List of dicts with canonical column names.

        Raises:
            GoldenSetImportError: If no valid header row is found.
        """
        all_rows: List[List[Optional[str]]] = []

        for row in worksheet.iter_rows(values_only=True):
            # Convert each cell value to sanitized string (or None)
            processed_row = [sanitize_text(cell) for cell in row]
            all_rows.append(processed_row)

        if not all_rows:
            raise GoldenSetImportError(
                message=f"Excel file '{file_name}' is empty.",
            )

        # Find the first non-empty row as header
        header_row: Optional[List[Optional[str]]] = None
        header_index: int = 0
        for i, row in enumerate(all_rows):
            non_empty_cells = [c for c in row if c is not None and str(c).strip()]
            if non_empty_cells:
                header_row = row
                header_index = i
                break

        if header_row is None:
            raise GoldenSetImportError(
                message=f"Excel file '{file_name}' has no header row.",
            )

        # Validate header has string values
        raw_headers: List[str] = []
        for cell in header_row:
            if cell is not None and str(cell).strip():
                raw_headers.append(str(cell).strip())
            else:
                raw_headers.append("")  # Empty column header placeholder

        if not any(h for h in raw_headers):
            raise GoldenSetImportError(
                message=f"Excel file '{file_name}' header row has no recognizable column names.",
            )

        # Build canonical column mapping
        column_map = build_column_mapping(raw_headers)
        golden_log.debug(
            "Excel column mapping: {mapping}",
            mapping=column_map,
        )

        # Extract data rows (skip header row)
        data_rows = all_rows[header_index + 1:]
        results: List[Dict[str, Optional[str]]] = []

        for data_row in data_rows:
            # Pad row to header length if needed
            padded = list(data_row) + [None] * max(0, len(raw_headers) - len(data_row))

            mapped_row: Dict[str, Optional[str]] = {}
            for col_idx, raw_header in enumerate(raw_headers):
                if not raw_header:
                    continue  # Skip empty header columns
                canonical = column_map.get(raw_header, raw_header.lower())
                cell_value = padded[col_idx] if col_idx < len(padded) else None
                mapped_row[canonical] = cell_value

            results.append(mapped_row)

        return results
