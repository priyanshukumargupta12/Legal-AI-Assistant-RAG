"""
dataset/scanner.py
==================
Dataset directory scanner — discovers and catalogues PDF files.

PURPOSE:
    Walks dataset/ directory, maps folders to categories, extracts
    file metadata, detects duplicates, identifies invalid PDFs,
    and generates DatasetStatistics.

SOLID: Single Responsibility — dataset discovery only.
"""

from __future__ import annotations

# TODO: Implement in Milestone 13 (Dataset Scanner + Export)


class DatasetScanner:
    """
    Scans dataset/ directory and produces DocumentMetadata list.

    Methods to implement:
        scan(dataset_root: str) -> Tuple[List[DocumentMetadata], DatasetStatistics]
        _get_category(folder_name: str) -> str
        _compute_md5(file_path: str) -> str
        _extract_page_count(file_path: str) -> int
        _detect_duplicates(documents: List[DocumentMetadata]) -> List[DocumentMetadata]
    """
    pass
