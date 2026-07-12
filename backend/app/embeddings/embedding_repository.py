"""
app/embeddings/embedding_repository.py
======================================
Repository layer for the Embedding Module.

PURPOSE:
    Handles file operations for loading document chunks from previous steps
    and writing the aggregated run statistics to disk. Adheres to clean
    architecture principles by abstracting details behind an interface.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from app.embeddings.embedding_logger import embedding_log
from app.embeddings.embedding_models import EmbeddingStatistics


class EmbeddingRepository(ABC):
    """
    Abstract repository for loading chunks and saving pipeline execution statistics.
    """

    @abstractmethod
    def load_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Load chunks generated for a specific document.

        Args:
            document_id: UUID of the document.

        Returns:
            List of raw chunk dictionaries.
        """
        ...

    @abstractmethod
    def save_embedding_statistics(self, statistics: EmbeddingStatistics) -> Path:
        """
        Persist execution statistics to disk.

        Args:
            statistics: EmbeddingStatistics domain object.

        Returns:
            Path to the written file.
        """
        ...


class FileSystemEmbeddingRepository(EmbeddingRepository):
    """
    File system implementation of EmbeddingRepository.
    """

    def __init__(self, metadata_dir: Path) -> None:
        """
        Initialize the repository with directories.

        Args:
            metadata_dir: Path to the metadata folder.
        """
        self.metadata_dir = metadata_dir
        self.chunks_dir = metadata_dir / "chunks"

    def load_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Reads from metadata/chunks/<document_id>_chunks.json and extracts chunks.
        """
        json_path = self.chunks_dir / f"{document_id}_chunks.json"
        if not json_path.exists():
            raise FileNotFoundError(
                f"Chunks JSON file for document '{document_id}' not found at '{json_path}'. "
                "Ensure chunker has run first."
            )

        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            embedding_log.error(
                "Failed to read chunks file | path={path} | error={error}",
                path=str(json_path),
                error=str(exc),
            )
            raise IOError(f"Failed to read chunks file: {exc}") from exc

        # Handle envelope format {"metadata": ..., "chunks": [...]}
        if isinstance(data, dict) and "chunks" in data:
            return data["chunks"]
        if isinstance(data, list):
            return data

        raise IOError(f"Malformed chunks file format in: {json_path}")

    def save_embedding_statistics(self, statistics: EmbeddingStatistics) -> Path:
        """
        Saves run statistics to metadata/embedding_statistics.json.
        """
        stats_path = self.metadata_dir / "embedding_statistics.json"

        stats_data = {
            "Total Chunks": statistics.total_chunks,
            "Embedded Chunks": statistics.embedded_chunks,
            "Failed Chunks": statistics.failed_chunks,
            "Average Embedding Time": round(statistics.average_embedding_time, 4),
            "Embedding Dimension": statistics.embedding_dimension,
            "processed_at": statistics.processed_at.isoformat(),
        }

        try:
            self.metadata_dir.mkdir(parents=True, exist_ok=True)
            with open(stats_path, "w", encoding="utf-8") as fh:
                json.dump(stats_data, fh, indent=2)
            embedding_log.info(
                "Saved embedding statistics | path={path} | chunks={chunks}",
                path=str(stats_path),
                chunks=statistics.embedded_chunks,
            )
            return stats_path
        except OSError as exc:
            embedding_log.error(
                "Failed to write embedding statistics | path={path} | error={error}",
                path=str(stats_path),
                error=str(exc),
            )
            raise IOError(f"Failed to write statistics file: {exc}") from exc
