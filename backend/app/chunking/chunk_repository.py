"""
app/chunking/chunk_repository.py
=================================
Repository layer for the Intelligent Chunking Module.

PURPOSE:
    Isolates all I/O operations (reading parsed JSON, writing chunks.json)
    behind an abstract interface. The service layer depends only on the
    abstract ChunkRepository, never on file-system specifics.

    This separation enables:
        - Swapping file-system storage for a database without touching services
        - Testing services with a mock repository (no real files needed)
        - Supporting future cloud storage (S3, GCS) by implementing a new class

DESIGN PATTERN:
    Repository Pattern — the repository is the sole owner of persistence logic.
    Service classes never call open(), json.load(), or os.path directly.

IMPLEMENTATIONS:
    FileSystemChunkRepository — Production implementation. Reads from
        metadata/parsed/<doc_id>.json and writes to metadata/chunks/<doc_id>_chunks.json.

OUTPUT FORMAT (chunks.json):
    [
      {
        "chunk_id": "1808ca0c_PAGE015_CHUNK003",
        "document_name": "Title11.pdf",
        "page": 15,
        "category": "Acts",
        "text": "..."
      },
      ...
    ]

SOLID:
    L — Liskov Substitution: FileSystemChunkRepository is a drop-in for
        ChunkRepository in all call sites.
    D — Dependency Inversion: Services depend on the abstract ChunkRepository,
        not the concrete file-system class.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List

from app.chunking.chunk_models import ChunkStatistics, DocumentChunk


# ─── Abstract Repository Interface ────────────────────────────────────────────

class ChunkRepository(ABC):
    """
    Abstract interface for all chunk persistence operations.

    Any concrete implementation must provide:
        1. A way to load raw parsed-page data (from PDF Parser output).
        2. A way to save the produced chunks as a structured JSON file.
        3. A way to load previously saved chunks (for retrieval/inspection).
    """

    @abstractmethod
    def load_parsed_document_json(self, json_path: Path) -> Dict:
        """
        Load the parsed document JSON produced by the PDF Parser.

        Args:
            json_path: Absolute path to the parser output JSON file.

        Returns:
            Dict with keys: document_id, document_name, category, pages[].

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError:           If reading or JSON parsing fails.
        """
        ...

    @abstractmethod
    def save_chunks_json(
        self,
        chunks: List[DocumentChunk],
        statistics: ChunkStatistics,
        output_path: Path,
    ) -> Path:
        """
        Serialize the list of DocumentChunk objects to a JSON file.

        The output JSON format matches the canonical schema:
            [{"chunk_id": ..., "document_name": ..., "page": ...,
              "category": ..., "text": ...}, ...]

        Args:
            chunks:      List of fully-formed DocumentChunk domain entities.
            statistics:  Run statistics to embed in the JSON envelope.
            output_path: Destination file path (parent dirs created automatically).

        Returns:
            The resolved Path of the written file.

        Raises:
            IOError: If the file cannot be written.
        """
        ...

    @abstractmethod
    def load_chunks_json(self, json_path: Path) -> List[Dict]:
        """
        Load a previously saved chunks.json file.

        Args:
            json_path: Absolute path to the chunks JSON file.

        Returns:
            List of chunk dicts matching the canonical schema.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError:           If reading or JSON parsing fails.
        """
        ...


# ─── File System Implementation ───────────────────────────────────────────────

class FileSystemChunkRepository(ChunkRepository):
    """
    Production implementation of ChunkRepository using the local file system.

    Reads from: metadata/parsed/<document_id>.json
    Writes to:  metadata/chunks/<document_id>_chunks.json

    Both paths are resolved relative to the project root via the caller
    (ChunkingService), keeping this class path-agnostic.
    """

    def load_parsed_document_json(self, json_path: Path) -> Dict:
        """
        Load a PDF Parser output JSON file.

        Args:
            json_path: Path to the parsed document JSON.

        Returns:
            Parsed dict with document metadata and pages list.

        Raises:
            FileNotFoundError: If no file exists at json_path.
            IOError:           If file reading or JSON decode fails.
        """
        if not json_path.exists():
            raise FileNotFoundError(
                f"Parsed JSON not found at '{json_path}'. "
                "Ensure the PDF Parser has been run for this document first."
            )
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:
            raise IOError(
                f"Invalid JSON in parsed file '{json_path}': {exc}"
            ) from exc
        except OSError as exc:
            raise IOError(
                f"Failed to read parsed JSON file '{json_path}': {exc}"
            ) from exc

    def save_chunks_json(
        self,
        chunks: List[DocumentChunk],
        statistics: ChunkStatistics,
        output_path: Path,
    ) -> Path:
        """
        Write DocumentChunk objects to a structured JSON file.

        The JSON envelope contains:
            - metadata: document identity + run statistics
            - chunks:   list of canonical chunk records

        Args:
            chunks:      All produced DocumentChunk objects.
            statistics:  Per-document chunking statistics.
            output_path: Destination path (parent directories auto-created).

        Returns:
            Resolved output_path after successful write.

        Raises:
            IOError: If the file cannot be created or written.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build canonical chunk records matching the chunks.json schema
        chunk_records = [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "document_name": c.document_name,
                "page": c.page_number,
                "category": c.category,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "chunk_size": c.chunk_size,
                "char_count": c.char_count,
                "token_estimate": c.token_estimate,
                "file_path": c.file_path,
                "source": c.source,
                "metadata": c.metadata,
            }
            for c in chunks
        ]

        # Build JSON envelope with statistics + chunks
        output_data = {
            "metadata": {
                "document_id": statistics.document_id,
                "document_name": statistics.document_name,
                "total_chunks": statistics.total_chunks,
                "avg_chunk_size": round(statistics.avg_chunk_size, 2),
                "max_chunk_size": statistics.max_chunk_size,
                "min_chunk_size": statistics.min_chunk_size,
                "chunks_per_page": {
                    str(k): v for k, v in statistics.chunks_per_page.items()
                },
                "processed_at": (
                    statistics.processed_at.isoformat()
                    if statistics.processed_at
                    else None
                ),
            },
            "chunks": chunk_records,
        }

        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(output_data, fh, indent=2, ensure_ascii=False)
            return output_path
        except OSError as exc:
            raise IOError(
                f"Failed to write chunks JSON to '{output_path}': {exc}"
            ) from exc

    def load_chunks_json(self, json_path: Path) -> List[Dict]:
        """
        Load a previously saved chunks JSON file.

        Supports both the envelope format ({"metadata": ..., "chunks": [...]})
        and the legacy flat list format ([{...}, {...}]) for backward compatibility.

        Args:
            json_path: Path to the chunks JSON file.

        Returns:
            List of chunk record dicts.

        Raises:
            FileNotFoundError: If json_path does not exist.
            IOError:           If reading or parsing fails.
        """
        if not json_path.exists():
            raise FileNotFoundError(
                f"Chunks JSON not found at '{json_path}'. "
                "Run the chunker for this document first."
            )
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise IOError(
                f"Invalid JSON in chunks file '{json_path}': {exc}"
            ) from exc
        except OSError as exc:
            raise IOError(
                f"Failed to read chunks JSON file '{json_path}': {exc}"
            ) from exc

        # Handle both envelope format and legacy flat list
        if isinstance(data, dict) and "chunks" in data:
            return data["chunks"]
        if isinstance(data, list):
            return data

        raise IOError(
            f"Unexpected format in chunks JSON '{json_path}': "
            "Expected list or dict with 'chunks' key."
        )
