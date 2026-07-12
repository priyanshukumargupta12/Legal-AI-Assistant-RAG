"""
app/dataset/__init__.py
========================
Dataset Management Module public interface.

Exports the key classes and the FastAPI router for use by main.py.
"""

from app.dataset.dataset_controller import router as dataset_router
from app.dataset.dataset_models import (
    DocumentRecord,
    DocumentStatus,
    DatasetStatistics,
    ScanResult,
)
from app.dataset.dataset_repository import (
    DatasetRepository,
    FileSystemDatasetRepository,
)
from app.dataset.dataset_schemas import (
    DocumentRecordSchema,
    DatasetStatisticsSchema,
    ScanResponseSchema,
)
from app.dataset.dataset_service import DatasetService

__all__ = [
    # Router
    "dataset_router",
    # Models
    "DocumentRecord",
    "DocumentStatus",
    "DatasetStatistics",
    "ScanResult",
    # Repository
    "DatasetRepository",
    "FileSystemDatasetRepository",
    # Schemas
    "DocumentRecordSchema",
    "DatasetStatisticsSchema",
    "ScanResponseSchema",
    # Service
    "DatasetService",
]
