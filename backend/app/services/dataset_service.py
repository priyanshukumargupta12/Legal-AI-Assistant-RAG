"""
services/dataset_service.py
============================
Service layer for dataset scanning and metadata export.

PURPOSE:
    Scans dataset/ directory, extracts metadata from every PDF,
    detects duplicates, generates documents.csv and documents.xlsx,
    and returns DatasetStatistics.

DEPENDENCIES (injected):
    - DatasetScanner (infrastructure)
    - DatasetExporter (infrastructure)

SOLID: Single Responsibility — dataset management only.
"""

from __future__ import annotations

# TODO: Implement in Milestone 13 (Dataset Scanner + Export)


class DatasetService:
    """
    Orchestrates dataset scanning and metadata export.

    Methods to implement:
        scan_dataset() -> DatasetScanResponse
        export_metadata() -> Path  (returns file path for download)
        get_statistics() -> DatasetStatistics
    """
    pass
