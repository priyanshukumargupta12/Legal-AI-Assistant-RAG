"""
app/chunking/chunk_service.py
==============================
Service layer orchestrating the Intelligent Chunking Module.

PURPOSE:
    Coordinates the full text-splitting pipeline:
        1. Receive LangChain Document objects from the PDF Parser.
        2. Validate each page's metadata.
        3. Split each page's text using RecursiveCharacterTextSplitter.
        4. Validate each produced chunk (empty, duplicate, too-short).
        5. Assemble DocumentChunk domain entities with full metadata.
        6. Calculate per-document and global chunking statistics.
        7. Persist chunks to metadata/chunks/<doc_id>_chunks.json.
        8. Return chunks + statistics to the caller.

WHY CHUNKING IS REQUIRED:
    LLM context windows are finite (typically 4K–128K tokens). A legal PDF
    can exceed 1,000 pages and millions of tokens. Without chunking:
        - The entire document cannot fit into a single LLM prompt.
        - Vector similarity search has no granularity — it can only match
          at the document level, not at the clause or paragraph level.
    Chunking converts long documents into fixed-size, semantically meaningful
    units that can each be embedded and retrieved independently.

ARCHITECTURE:
    ChunkingService uses Dependency Injection — it receives its dependencies
    (repository, splitter, output_dir) via the constructor. This makes the
    service completely decoupled from infrastructure concerns and trivially
    testable with mock objects.

PROCESSING MODEL:
    - Documents are processed one at a time (memory-efficient).
    - Batch processing (chunk_multiple_documents) calls chunk_langchain_documents
      in a loop, making it trivially parallelizable with concurrent.futures
      in a future version.

SOLID:
    S — Single Responsibility: Only orchestrates splitting + statistics.
    O — Open/Closed: New validators can be added without modifying existing logic.
    D — Dependency Inversion: Depends on ChunkRepository abstraction.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.chunking.chunk_logger import chunk_log
from app.chunking.chunk_models import ChunkStatistics, DocumentChunk, GlobalChunkStats
from app.chunking.chunk_repository import ChunkRepository
from app.chunking.chunk_utils import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    build_chunk_metadata,
    build_text_splitter,
    clean_chunk_text,
    estimate_token_count,
    generate_chunk_id,
    is_empty_chunk,
    is_too_short,
    validate_chunk_metadata,
)
from app.core.exceptions import ChunkingError


class ChunkingService:
    """
    Orchestrates the full intelligent text chunking pipeline.

    Responsibilities:
        - Accept LangChain Document objects from PDF Parser.
        - Validate page metadata before splitting.
        - Apply RecursiveCharacterTextSplitter with configured strategy.
        - Detect and discard empty / duplicate / too-short chunks.
        - Build DocumentChunk domain entities with complete metadata.
        - Calculate per-document statistics.
        - Persist output via the injected ChunkRepository.

    Design:
        Uses Dependency Injection for the repository and splitter, enabling
        unit testing without touching the file system. Stateless across calls
        — each call to chunk_langchain_documents() is fully independent.

    Args:
        repository:  Abstract chunk persistence layer.
        output_dir:  Directory where chunks.json files are written.
        chunk_size:  Target chunk character length (default 500).
        chunk_overlap: Overlap character count between chunks (default 100).
    """

    def __init__(
        self,
        repository: ChunkRepository,
        output_dir: Path,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ) -> None:
        self._repository = repository
        self._output_dir = output_dir
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

        # Build the text splitter once — it is stateless and thread-safe.
        # Separator priority: Paragraph → Sentence → Line → Word → Character
        self._splitter: RecursiveCharacterTextSplitter = build_text_splitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        chunk_log.info(
            "ChunkingService initialised | chunk_size={size} | overlap={overlap}",
            size=chunk_size,
            overlap=chunk_overlap,
        )

    # ─── Primary Public Interface ─────────────────────────────────────────────

    def chunk_langchain_documents(
        self,
        docs: List[Document],
    ) -> Tuple[List[DocumentChunk], ChunkStatistics]:
        """
        Split a list of LangChain Document objects (one per page) into chunks.

        This is the primary entry point for the Embedding Pipeline. The PDF
        Parser calls this method after producing one LangChain Document per page.

        Processing steps (per document):
            1. Validate input list is non-empty.
            2. Extract document identity from the first document's metadata.
            3. For each page Document:
                a. Validate page metadata.
                b. Skip empty pages (log warning).
                c. Split page text with RecursiveCharacterTextSplitter.
                d. For each split:
                    - Clean text (strip, collapse whitespace).
                    - Skip empty / too-short splits.
                    - Check for intra-document duplicates via text hash.
                    - Build DocumentChunk domain entity.
                    - Log chunk creation.
            4. Calculate per-document statistics.
            5. Persist chunks.json via repository.
            6. Return (chunks, statistics).

        Args:
            docs: List of LangChain Document objects. Each represents one
                  page of a single PDF document. All docs must share the
                  same document_id in their metadata.

        Returns:
            Tuple of:
                - List[DocumentChunk]: All valid chunks produced.
                - ChunkStatistics: Aggregate statistics for this document.

        Raises:
            ChunkingError: If docs is empty or a critical processing error occurs.
        """
        if not docs:
            raise ChunkingError("No LangChain documents provided to ChunkingService.")

        # ── Extract document identity from first page metadata ─────────────────
        first_meta = docs[0].metadata
        doc_id = str(first_meta.get("document_id", "UNKNOWN"))
        doc_name = str(first_meta.get("document_name", "unknown.pdf"))
        category = str(first_meta.get("category", "unknown"))
        file_path = str(first_meta.get("file_path", "unknown"))

        chunk_log.info(
            "Chunking started | document={name} | id={id} | total_pages={pages}",
            name=doc_name,
            id=doc_id,
            pages=len(docs),
        )

        start_time = time.perf_counter()

        all_chunks: List[DocumentChunk] = []
        chunks_per_page: Dict[int, int] = {}

        # Track hashes of chunk texts to detect intra-document duplicates
        seen_text_hashes: set[int] = set()

        for doc in docs:
            page_chunks = self._process_page(
                doc=doc,
                doc_id=doc_id,
                doc_name=doc_name,
                category=category,
                file_path=file_path,
                seen_text_hashes=seen_text_hashes,
            )
            if page_chunks:
                page_num = doc.metadata.get("page_number") or 0
                chunks_per_page[int(page_num)] = len(page_chunks)
                all_chunks.extend(page_chunks)

        # ── Build statistics ───────────────────────────────────────────────────
        statistics = self._calculate_statistics(
            doc_id=doc_id,
            doc_name=doc_name,
            chunks=all_chunks,
            chunks_per_page=chunks_per_page,
        )

        # ── Persist output JSON ────────────────────────────────────────────────
        output_path = self._output_dir / f"{doc_id}_chunks.json"
        self._repository.save_chunks_json(all_chunks, statistics, output_path)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        chunk_log.info(
            "Chunking complete | document={name} | total_chunks={total} "
            "| avg_size={avg:.1f} chars | elapsed={elapsed:.2f}ms",
            name=doc_name,
            total=statistics.total_chunks,
            avg=statistics.avg_chunk_size,
            elapsed=elapsed_ms,
        )

        self._log_statistics(statistics)

        return all_chunks, statistics

    def chunk_by_document_id(
        self,
        document_id: str,
        parsed_dir: Path,
    ) -> Tuple[List[DocumentChunk], ChunkStatistics]:
        """
        Load a parsed document JSON and perform chunking.

        Bridges the PDF Parser file-system output (metadata/parsed/<id>.json)
        to the Chunking Module, reconstructing LangChain Document objects
        from the stored parsed page data.

        Args:
            document_id: UUID of the document to chunk.
            parsed_dir:  Directory containing PDF Parser output JSON files.

        Returns:
            Tuple of (List[DocumentChunk], ChunkStatistics).

        Raises:
            ChunkingError: If the parsed JSON cannot be found or loaded.
        """
        json_path = parsed_dir / f"{document_id}.json"

        chunk_log.info(
            "Loading parsed JSON for chunking | id={id} | path={path}",
            id=document_id,
            path=str(json_path),
        )

        try:
            parsed_data = self._repository.load_parsed_document_json(json_path)
        except FileNotFoundError as exc:
            raise ChunkingError(
                f"Parsed JSON not found for document '{document_id}'. "
                "Run the PDF Parser first.",
                document_id=document_id,
            ) from exc
        except IOError as exc:
            raise ChunkingError(
                f"Failed to load parsed JSON for document '{document_id}': {exc}",
                document_id=document_id,
            ) from exc

        # Reconstruct LangChain Document objects from parsed pages
        docs = self._reconstruct_langchain_docs(parsed_data)

        return self.chunk_langchain_documents(docs)

    def chunk_multiple_documents(
        self,
        document_ids: List[str],
        parsed_dir: Path,
    ) -> GlobalChunkStats:
        """
        Chunk multiple documents sequentially and return global statistics.

        Processes one document at a time to control memory usage. Each document
        is independently chunked and its chunks.json written before moving to
        the next. This design supports future parallelisation with
        concurrent.futures.ProcessPoolExecutor without architectural changes.

        Args:
            document_ids: List of document UUIDs to process.
            parsed_dir:   Directory containing parser output JSON files.

        Returns:
            GlobalChunkStats summarising the entire batch run.
        """
        run_started_at = datetime.now(tz=timezone.utc)
        all_sizes: List[int] = []
        chunks_per_document: Dict[str, int] = {}
        failed_documents: List[str] = []

        chunk_log.info(
            "Batch chunking started | total_documents={total}",
            total=len(document_ids),
        )

        for doc_id in document_ids:
            try:
                chunks, stats = self.chunk_by_document_id(doc_id, parsed_dir)
                chunks_per_document[doc_id] = stats.total_chunks
                all_sizes.extend(c.char_count for c in chunks)

                chunk_log.info(
                    "Document chunked | id={id} | chunks={n}",
                    id=doc_id,
                    n=stats.total_chunks,
                )

            except ChunkingError as exc:
                chunk_log.error(
                    "Document chunking failed | id={id} | error={error}",
                    id=doc_id,
                    error=str(exc),
                )
                failed_documents.append(doc_id)

        run_completed_at = datetime.now(tz=timezone.utc)

        global_stats = GlobalChunkStats(
            total_documents=len(document_ids) - len(failed_documents),
            total_chunks=sum(chunks_per_document.values()),
            avg_chunk_size=sum(all_sizes) / len(all_sizes) if all_sizes else 0.0,
            max_chunk_size=max(all_sizes) if all_sizes else 0,
            min_chunk_size=min(all_sizes) if all_sizes else 0,
            chunks_per_document=chunks_per_document,
            failed_documents=failed_documents,
            run_started_at=run_started_at,
            run_completed_at=run_completed_at,
        )

        chunk_log.info(
            "Batch chunking complete | processed={ok} | failed={fail} "
            "| total_chunks={total} | avg_size={avg:.1f}",
            ok=global_stats.total_documents,
            fail=len(failed_documents),
            total=global_stats.total_chunks,
            avg=global_stats.avg_chunk_size,
        )

        return global_stats

    # ─── Internal Processing Helpers ─────────────────────────────────────────

    def _process_page(
        self,
        doc: Document,
        doc_id: str,
        doc_name: str,
        category: str,
        file_path: str,
        seen_text_hashes: set[int],
    ) -> List[DocumentChunk]:
        """
        Process a single page LangChain Document into zero or more chunks.

        Args:
            doc:               LangChain Document representing one PDF page.
            doc_id:            Parent document UUID.
            doc_name:          PDF filename.
            category:          Document category.
            file_path:         Absolute path to the source PDF.
            seen_text_hashes:  Mutable set of hashes for duplicate detection.

        Returns:
            List of valid DocumentChunk objects for this page (may be empty).
        """
        meta = doc.metadata
        page_num = meta.get("page_number")

        # ── Missing page number: log warning and use fallback ─────────────────
        if page_num is None:
            chunk_log.warning(
                "Missing page_number in metadata | document={name} | using fallback=0",
                name=doc_name,
            )
            page_num = 0
        page_num = int(page_num)

        chunk_log.debug(
            "Page processing started | document={name} | page={page}",
            name=doc_name,
            page=page_num,
        )

        # ── Validate metadata ─────────────────────────────────────────────────
        validation_errors = validate_chunk_metadata(meta)
        if validation_errors:
            chunk_log.warning(
                "Metadata validation errors | document={name} | page={page} | errors={errors}",
                name=doc_name,
                page=page_num,
                errors=" | ".join(validation_errors),
            )

        # ── Skip empty pages ───────────────────────────────────────────────────
        page_text = doc.page_content
        if is_empty_chunk(page_text):
            chunk_log.warning(
                "Empty page skipped | document={name} | page={page}",
                name=doc_name,
                page=page_num,
            )
            return []

        # ── Split page text with Section Headings Preservation ──────────────────
        headings = []
        heading_matches = re.finditer(
            r"^(PART\s+[0-9A-Z\-\.\s]+|SUBCHAPTER\s+[A-Z\-\.\s]+|§\s*[0-9]+[a-zA-Z0-9\-\.\:]*|Sec(tion)?\s*\.?\s*[0-9]+[a-zA-Z0-9\-\.\:]*|[A-Z0-9\s,\-\:\(\)]{8,80})$",
            page_text,
            re.MULTILINE
        )
        for match in heading_matches:
            headings.append((match.start(), match.group(0).strip()))

        raw_splits = self._splitter.split_text(page_text)
        page_chunks: List[DocumentChunk] = []
        chunk_index = 0
        search_start_pos = 0

        for raw_split in raw_splits:
            # Find the position of the split inside page_text
            split_pos = page_text.find(raw_split, search_start_pos)
            if split_pos != -1:
                search_start_pos = split_pos + len(raw_split)
            else:
                split_pos = page_text.find(raw_split)  # fallback
            
            # Find active heading before the split position
            active_heading = ""
            if headings:
                for h_start, h_text in headings:
                    if h_start <= split_pos:
                        active_heading = h_text
                    else:
                        break
            
            # Prepend the active heading to the chunk text if found
            final_text = raw_split
            if active_heading:
                final_text = f"[{active_heading}] {raw_split}"

            chunk = self._build_chunk(
                raw_text=final_text,
                doc_id=doc_id,
                doc_name=doc_name,
                category=category,
                page_num=page_num,
                file_path=file_path,
                chunk_index=chunk_index,
                seen_text_hashes=seen_text_hashes,
            )
            if chunk is not None:
                page_chunks.append(chunk)
                chunk_index += 1

        chunk_log.debug(
            "Page processed | document={name} | page={page} | chunks_produced={n}",
            name=doc_name,
            page=page_num,
            n=len(page_chunks),
        )

        return page_chunks

    def _build_chunk(
        self,
        raw_text: str,
        doc_id: str,
        doc_name: str,
        category: str,
        page_num: int,
        file_path: str,
        chunk_index: int,
        seen_text_hashes: set[int],
    ) -> Optional[DocumentChunk]:
        """
        Validate a raw text split and build a DocumentChunk if it passes.

        Validation gates (in order):
            1. Empty text  → skip
            2. Too short   → skip (below MIN_CHUNK_LENGTH)
            3. Duplicate   → skip (same hash already in seen_text_hashes)

        Args:
            raw_text:          Text produced by RecursiveCharacterTextSplitter.
            doc_id:            Parent document UUID.
            doc_name:          PDF filename.
            category:          Document category.
            page_num:          1-based page number.
            file_path:         Source PDF path.
            chunk_index:       0-based index within the current page.
            seen_text_hashes:  Mutable set tracking processed text hashes.

        Returns:
            DocumentChunk domain entity, or None if any validation gate fails.
        """
        # Gate 1: Empty chunk
        cleaned_text = clean_chunk_text(raw_text)
        if is_empty_chunk(cleaned_text):
            chunk_log.debug(
                "Empty chunk discarded | document={name} | page={page} | index={idx}",
                name=doc_name,
                page=page_num,
                idx=chunk_index,
            )
            return None

        # Gate 2: Too short
        if is_too_short(cleaned_text):
            chunk_log.debug(
                "Chunk too short discarded | document={name} | page={page} "
                "| index={idx} | length={length}",
                name=doc_name,
                page=page_num,
                idx=chunk_index,
                length=len(cleaned_text),
            )
            return None

        # Gate 3: Duplicate text within this document
        text_hash = hash(cleaned_text)
        if text_hash in seen_text_hashes:
            chunk_log.warning(
                "Duplicate chunk discarded | document={name} | page={page} | index={idx}",
                name=doc_name,
                page=page_num,
                idx=chunk_index,
            )
            return None
        seen_text_hashes.add(text_hash)

        # ── Build chunk ID and metadata ────────────────────────────────────────
        chunk_id = generate_chunk_id(doc_id, page_num, chunk_index)
        char_count = len(cleaned_text)
        token_estimate = estimate_token_count(cleaned_text)
        chunk_metadata = build_chunk_metadata(
            document_id=doc_id,
            document_name=doc_name,
            category=category,
            page_number=page_num,
            file_path=file_path,
        )

        chunk = DocumentChunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            document_name=doc_name,
            category=category,
            page_number=page_num,
            chunk_index=chunk_index,
            text=cleaned_text,
            chunk_size=self._chunk_size,   # configured target size
            char_count=char_count,          # actual size
            token_estimate=token_estimate,
            file_path=file_path,
            source=doc_name,
            metadata=chunk_metadata,
        )

        chunk_log.debug(
            "Chunk created | id={cid} | page={page} | chars={chars} | tokens={tokens}",
            cid=chunk_id,
            page=page_num,
            chars=char_count,
            tokens=token_estimate,
        )

        return chunk

    # ─── Statistics Helpers ───────────────────────────────────────────────────

    def _calculate_statistics(
        self,
        doc_id: str,
        doc_name: str,
        chunks: List[DocumentChunk],
        chunks_per_page: Dict[int, int],
    ) -> ChunkStatistics:
        """
        Compute aggregate statistics for a completed chunking run.

        Args:
            doc_id:         Parent document UUID.
            doc_name:       PDF filename.
            chunks:         All valid chunks produced.
            chunks_per_page: Dict mapping page_number → chunk count.

        Returns:
            ChunkStatistics with all fields populated.
        """
        if not chunks:
            return ChunkStatistics(
                document_id=doc_id,
                document_name=doc_name,
                total_chunks=0,
                avg_chunk_size=0.0,
                max_chunk_size=0,
                min_chunk_size=0,
                chunks_per_page={},
            )

        sizes = [c.char_count for c in chunks]
        return ChunkStatistics(
            document_id=doc_id,
            document_name=doc_name,
            total_chunks=len(chunks),
            avg_chunk_size=sum(sizes) / len(sizes),
            max_chunk_size=max(sizes),
            min_chunk_size=min(sizes),
            chunks_per_page=chunks_per_page,
            processed_at=datetime.now(tz=timezone.utc),
        )

    def _log_statistics(self, statistics: ChunkStatistics) -> None:
        """
        Emit a structured statistics log entry after chunking completes.

        Args:
            statistics: The computed ChunkStatistics for the current document.
        """
        chunk_log.info(
            "Chunk statistics | document={name} | total={total} "
            "| avg={avg:.1f} | max={max} | min={min} | pages={pages}",
            name=statistics.document_name,
            total=statistics.total_chunks,
            avg=statistics.avg_chunk_size,
            max=statistics.max_chunk_size,
            min=statistics.min_chunk_size,
            pages=len(statistics.chunks_per_page),
        )

    # ─── Document Reconstruction ──────────────────────────────────────────────

    def _reconstruct_langchain_docs(self, parsed_data: dict) -> List[Document]:
        """
        Reconstruct LangChain Document objects from a parsed document JSON dict.

        Called by chunk_by_document_id() when loading from file system rather
        than receiving docs directly from the PDF Parser.

        Args:
            parsed_data: Dict loaded from metadata/parsed/<doc_id>.json.

        Returns:
            List of LangChain Document objects, one per page.
        """
        document_id = str(parsed_data.get("document_id", "UNKNOWN"))
        doc_name = str(parsed_data.get("document_name", "unknown.pdf"))
        category = str(parsed_data.get("category", "unknown"))
        file_path = f"dataset/{category}/{doc_name}"

        docs: List[Document] = []
        for page_entry in parsed_data.get("pages", []):
            page_num = page_entry.get("page")
            page_text = page_entry.get("text", "")

            lc_doc = Document(
                page_content=page_text,
                metadata=build_chunk_metadata(
                    document_id=document_id,
                    document_name=doc_name,
                    category=category,
                    page_number=int(page_num) if page_num is not None else 0,
                    file_path=file_path,
                ),
            )
            docs.append(lc_doc)

        chunk_log.debug(
            "Reconstructed LangChain docs from JSON | document={name} | pages={pages}",
            name=doc_name,
            pages=len(docs),
        )
        return docs
