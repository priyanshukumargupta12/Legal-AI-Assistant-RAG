"""
app/knowledge/knowledge_repository.py
=======================================
Persistence layer for the OKF Standardization Module.

PURPOSE:
    Implements all file I/O for the knowledge standardization pipeline:
        READ  — Discovers and loads chunk JSON files from metadata/chunks/
        WRITE — Persists knowledge.json and knowledge_chunks.json to metadata/knowledge/

    KnowledgeRepository is the ONLY class that touches the file system for
    OKF data. All other knowledge module components use it via DI.

STORAGE LAYOUT:
    metadata/knowledge/
    ├── knowledge.json         — Array of KnowledgeDocument objects (per-PDF)
    └── knowledge_chunks.json  — Array of KnowledgeChunk objects (per-chunk)

DESIGN:
    - Atomic write (write to .tmp → os.replace) prevents corruption on crash.
    - Chunk files are loaded lazily on build — no in-memory caching of raw chunks.
    - load_knowledge_documents() and load_knowledge_chunks() restore from disk
      on service initialization (same pattern as GraphRepository).

SOLID:
    Single Responsibility — file I/O only; no extraction logic.
    Dependency Inversion — KnowledgeBuilder depends on KnowledgeRepository.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from app.knowledge.knowledge_logger import knowledge_log
from app.knowledge.knowledge_models import KnowledgeChunk, KnowledgeDocument


class KnowledgeRepository:
    """
    File-system backed persistence for OKF knowledge objects.

    Manages two JSON output files:
        knowledge.json         — serialized KnowledgeDocument objects
        knowledge_chunks.json  — serialized KnowledgeChunk objects

    And reads chunk source files from:
        metadata/chunks/<doc_id>_chunks.json

    Constructor Args:
        storage_dir: Absolute path to metadata/knowledge/ directory.
        chunks_dir:  Absolute path to metadata/chunks/ directory.
    """

    def __init__(self, storage_dir: Path, chunks_dir: Path) -> None:
        """
        Initialize the repository and ensure storage directory exists.

        Args:
            storage_dir: Where OKF JSON files are written.
            chunks_dir:  Where chunk JSON files are read from.
        """
        self._storage_dir = storage_dir
        self._chunks_dir = chunks_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._docs_path = self._storage_dir / "knowledge.json"
        self._chunks_path = self._storage_dir / "knowledge_chunks.json"

        knowledge_log.info(
            "KnowledgeRepository initialized | storage={storage} | chunks={chunks}",
            storage=str(self._storage_dir),
            chunks=str(self._chunks_dir),
        )

    # =========================================================================
    # SAVE OPERATIONS
    # =========================================================================

    def save_documents(self, documents: List[KnowledgeDocument]) -> None:
        """
        Persist all KnowledgeDocument objects to knowledge.json.

        Args:
            documents: List of KnowledgeDocument instances to serialize.
        """
        data = [doc.to_dict() for doc in documents]
        self._atomic_write(self._docs_path, data)
        knowledge_log.info(
            "Saved knowledge documents | count={count} | path={path}",
            count=len(documents),
            path=str(self._docs_path),
        )

    def save_chunks(self, chunks: List[KnowledgeChunk]) -> None:
        """
        Persist all KnowledgeChunk objects to knowledge_chunks.json.

        Args:
            chunks: List of KnowledgeChunk instances to serialize.
        """
        data = [chunk.to_dict() for chunk in chunks]
        self._atomic_write(self._chunks_path, data)
        knowledge_log.info(
            "Saved knowledge chunks | count={count} | path={path}",
            count=len(chunks),
            path=str(self._chunks_path),
        )

    def save_all(
        self,
        documents: List[KnowledgeDocument],
        chunks: List[KnowledgeChunk],
    ) -> None:
        """
        Persist all knowledge objects in a single operation.

        Args:
            documents: KnowledgeDocument objects (one per PDF).
            chunks:    KnowledgeChunk objects (one per source chunk).
        """
        self.save_documents(documents)
        self.save_chunks(chunks)
        knowledge_log.info(
            "All knowledge data saved | documents={d} | chunks={c}",
            d=len(documents),
            c=len(chunks),
        )

    # =========================================================================
    # LOAD OPERATIONS
    # =========================================================================

    def load_knowledge_documents(self) -> List[KnowledgeDocument]:
        """
        Load all KnowledgeDocument objects from knowledge.json.

        Returns:
            List of deserialized KnowledgeDocument instances.
            Empty list if file does not exist.
        """
        if not self._docs_path.exists():
            knowledge_log.warning("knowledge.json not found — OKF not yet built")
            return []

        raw = self._read_json(self._docs_path)
        docs = [KnowledgeDocument.from_dict(item) for item in raw]
        knowledge_log.info("Loaded knowledge documents | count={count}", count=len(docs))
        return docs

    def load_knowledge_chunks(self) -> List[KnowledgeChunk]:
        """
        Load all KnowledgeChunk objects from knowledge_chunks.json.

        Returns:
            List of deserialized KnowledgeChunk instances.
            Empty list if file does not exist.
        """
        if not self._chunks_path.exists():
            knowledge_log.warning("knowledge_chunks.json not found — OKF not yet built")
            return []

        raw = self._read_json(self._chunks_path)
        chunks = [KnowledgeChunk.from_dict(item) for item in raw]
        knowledge_log.info("Loaded knowledge chunks | count={count}", count=len(chunks))
        return chunks

    # =========================================================================
    # CHUNK SOURCE DISCOVERY AND LOADING
    # =========================================================================

    def discover_chunk_files(self) -> List[Path]:
        """
        Discover all chunk JSON files in the chunks directory.

        Returns:
            Sorted list of Path objects pointing to chunk JSON files.
        """
        if not self._chunks_dir.exists():
            knowledge_log.warning(
                "Chunks directory does not exist | dir={dir}",
                dir=str(self._chunks_dir),
            )
            return []

        files = sorted(self._chunks_dir.rglob("*_chunks.json"))
        if not files:
            files = sorted(self._chunks_dir.rglob("*.json"))

        knowledge_log.info(
            "Discovered chunk files | count={count}",
            count=len(files),
        )
        return files

    def load_raw_chunks_from_file(self, path: Path) -> List[Dict]:
        """
        Load and parse a single chunk JSON file.

        Handles both list-of-chunks format and dict-with-"chunks"-key format.

        Args:
            path: Path to a chunk JSON file.

        Returns:
            List of raw chunk dictionaries.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("chunks", [])
        return []

    def iter_chunk_batches(
        self,
        batch_size: int = 500,
    ) -> Iterator[Tuple[str, List[Dict]]]:
        """
        Iterate over all chunk files, yielding (doc_name, chunk_list) tuples.

        Yields chunks grouped by document name in batches for memory efficiency.
        Documents are processed one at a time — no full dataset in memory.

        Args:
            batch_size: Maximum chunks to load from one file at a time (not used
                        for truncation — all chunks from a file are loaded together).
                        Reserved for future streaming support.

        Yields:
            (document_name, chunk_list) tuples, one per chunk file.
        """
        chunk_files = self.discover_chunk_files()
        for path in chunk_files:
            try:
                chunks = self.load_raw_chunks_from_file(path)
                if not chunks:
                    continue
                # Determine document name from first chunk
                first = chunks[0]
                doc_name = first.get("document_name", first.get("source", path.stem))
                yield doc_name, chunks
            except Exception as exc:  # noqa: BLE001
                knowledge_log.error(
                    "Failed to load chunk file | file={f} | error={e}",
                    f=path.name,
                    e=str(exc),
                )

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def knowledge_exists(self) -> bool:
        """Return True if both OKF output files exist on disk."""
        return self._docs_path.exists() and self._chunks_path.exists()

    def get_storage_paths(self) -> Dict[str, str]:
        """Return all storage file paths as a dictionary."""
        return {
            "knowledge_documents": str(self._docs_path),
            "knowledge_chunks": str(self._chunks_path),
            "storage_directory": str(self._storage_dir),
        }

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _atomic_write(self, path: Path, data: object) -> None:
        """
        Write JSON data atomically using a temp file and atomic rename.

        Prevents partial/corrupt files if the process is interrupted mid-write.

        Args:
            path: Target file path.
            data: JSON-serializable object to write.
        """
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            os.replace(tmp_path, path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    def _read_json(self, path: Path) -> List:
        """
        Read and parse a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed JSON list.
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
