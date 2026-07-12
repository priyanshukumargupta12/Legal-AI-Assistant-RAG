"""
scripts/batch_parse_and_chunk.py
==================================
Batch Pipeline: Parse → Chunk all 96 valid PDF documents.

PURPOSE:
    Reads documents.csv, filters valid (non-duplicate) documents,
    runs PDFParserService on each, then ChunkingService on the output.
    Produces one parsed JSON and one chunks JSON per document.

USAGE:
    From the backend directory:
        .\\venv\\Scripts\\python.exe scripts/batch_parse_and_chunk.py

    With optional flags:
        --skip-parsed       Skip documents already parsed (resume support)
        --skip-chunked      Skip documents already chunked (resume support)
        --category CATEGORY Process only one category (Acts/Tax/CourtJudgement/Legal_opinion)
        --limit N           Process only the first N documents (for testing)
        --chunk-only        Skip parsing, only chunk already-parsed documents

OUTPUT:
    metadata/parsed/<document_id>.json     — PDF Parser output
    metadata/chunks/<document_id>_chunks.json — Chunker output
    logs/dataset/dataset.log               — Full structured log

ARCHITECTURE:
    Sequential processing (one document at a time) for memory efficiency.
    Each document is fully parsed + chunked before moving to the next.
    Supports future parallelisation with concurrent.futures.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Ensure backend root is on the Python path ─────────────────────────────────
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import pandas as pd

from app.chunking.chunk_repository import FileSystemChunkRepository
from app.chunking.chunk_service import ChunkingService
from app.core.config import get_settings
from app.core.exceptions import ChunkingError, PDFParseError
from app.logging.logger import configure_logging, get_logger
from app.pdf_parser.parser_repository import FileSystemParserRepository
from app.pdf_parser.parser_service import PDFParserService

# ── Paths ─────────────────────────────────────────────────────────────────────
METADATA_DIR = BACKEND_ROOT.parent / "metadata"
DATASET_DIR  = BACKEND_ROOT.parent / "dataset"
PARSED_DIR   = METADATA_DIR / "parsed"
CHUNKS_DIR   = METADATA_DIR / "chunks"
REGISTRY_CSV = METADATA_DIR / "documents.csv"

# ── Chunking configuration (dynamically loaded from settings) ──────────────────
settings = get_settings()
CHUNK_SIZE    = settings.chunk_size
CHUNK_OVERLAP = settings.chunk_overlap

# ── Logger ────────────────────────────────────────────────────────────────────
configure_logging(log_level="INFO")
log = get_logger("dataset")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_documents(
    category: str | None,
    limit: int | None,
    skip_status: tuple[str, ...] = ("duplicate",),
) -> list[dict]:
    """
    Load and filter documents from documents.csv.

    Args:
        category:    If set, only include documents of this category.
        limit:       If set, cap the number of documents returned.
        skip_status: Rows with these Status values are excluded.

    Returns:
        List of row dicts from the CSV.
    """
    if not REGISTRY_CSV.exists():
        log.error("Registry CSV not found at '{path}'", path=str(REGISTRY_CSV))
        sys.exit(1)

    df = pd.read_csv(REGISTRY_CSV)

    # Filter out non-valid documents (duplicates, errors)
    df = df[~df["Status"].isin(skip_status)]

    if category:
        df = df[df["Category"] == category]

    if limit:
        df = df.head(limit)

    log.info(
        "Loaded {count} documents to process | category={cat} | limit={lim}",
        count=len(df),
        cat=category or "ALL",
        lim=limit or "NONE",
    )
    return df.to_dict("records")


def build_parser_service() -> PDFParserService:
    """Create a configured PDFParserService instance."""
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    return PDFParserService(
        repository=FileSystemParserRepository(),
        registry_csv_path=REGISTRY_CSV,
        output_dir=PARSED_DIR,
    )


def build_chunking_service() -> ChunkingService:
    """Create a configured ChunkingService instance."""
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    return ChunkingService(
        repository=FileSystemChunkRepository(),
        output_dir=CHUNKS_DIR,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )


def is_already_parsed(document_id: str) -> bool:
    """Return True if a parsed JSON already exists for this document."""
    return (PARSED_DIR / f"{document_id}.json").exists()


def is_already_chunked(document_id: str) -> bool:
    """Return True if a chunks JSON already exists for this document."""
    return (CHUNKS_DIR / f"{document_id}_chunks.json").exists()


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    skip_parsed: bool,
    skip_chunked: bool,
    chunk_only: bool,
    category: str | None,
    limit: int | None,
) -> None:
    """
    Execute the full parse → chunk batch pipeline.

    Args:
        skip_parsed:  If True, skip documents that already have a parsed JSON.
        skip_chunked: If True, skip documents that already have a chunks JSON.
        chunk_only:   If True, skip parsing and only chunk existing parsed JSONs.
        category:     Filter by category name (optional).
        limit:        Maximum number of documents to process (optional).
    """
    pipeline_start = time.perf_counter()
    run_started_at = datetime.now(tz=timezone.utc)

    documents = load_documents(category=category, limit=limit)
    total_docs = len(documents)

    if total_docs == 0:
        log.warning("No documents found to process. Check your filters.")
        return

    # ── Initialise services ────────────────────────────────────────────────────
    parser_service  = build_parser_service()
    chunker_service = build_chunking_service()

    # ── Counters ───────────────────────────────────────────────────────────────
    parse_ok       = 0
    parse_skipped  = 0
    parse_failed   = 0
    chunk_ok       = 0
    chunk_skipped  = 0
    chunk_failed   = 0
    total_chunks   = 0
    failed_docs: list[dict] = []

    print()
    print("=" * 70)
    print(f"  BATCH PARSE -> CHUNK PIPELINE")
    print(f"  Documents : {total_docs}")
    print(f"  Chunk Size: {CHUNK_SIZE} chars  |  Overlap: {CHUNK_OVERLAP} chars")
    print(f"  Started   : {run_started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print()

    for doc_idx, doc in enumerate(documents, start=1):
        doc_id   = str(doc["Document_ID"])
        doc_name = str(doc["File_Name"])
        category_name = str(doc["Category"])
        file_path = Path(str(doc["File_Path"]))

        print(f"[{doc_idx:3d}/{total_docs}] {doc_name}  ({category_name})")

        # ── STEP 1: PARSE ──────────────────────────────────────────────────────
        langchain_docs = None

        if chunk_only:
            # Chunk-only mode: skip parsing entirely
            print(f"         Parse: SKIPPED (chunk-only mode)")
            parse_skipped += 1

        elif skip_parsed and is_already_parsed(doc_id):
            print(f"         Parse: SKIPPED (already parsed)")
            parse_skipped += 1

        else:
            parse_start = time.perf_counter()
            try:
                log.info(
                    "Parse started | doc={name} | id={id}",
                    name=doc_name, id=doc_id,
                )
                parsed_doc, langchain_docs = parser_service.parse_document(doc_id)
                parse_elapsed = time.perf_counter() - parse_start
                print(
                    f"         Parse: OK  | {parsed_doc.total_pages} pages "
                    f"| {format_duration(parse_elapsed)}"
                )
                parse_ok += 1

            except (PDFParseError, FileNotFoundError, Exception) as exc:
                parse_elapsed = time.perf_counter() - parse_start
                print(f"         Parse: FAILED — {exc}")
                log.error(
                    "Parse failed | doc={name} | id={id} | error={error}",
                    name=doc_name, id=doc_id, error=str(exc),
                )
                parse_failed += 1
                failed_docs.append({
                    "document_id": doc_id,
                    "document_name": doc_name,
                    "stage": "parse",
                    "error": str(exc),
                })
                # Cannot chunk without parsing — skip to next document
                print()
                continue

        # ── STEP 2: CHUNK ──────────────────────────────────────────────────────
        if skip_chunked and is_already_chunked(doc_id):
            print(f"         Chunk: SKIPPED (already chunked)")
            chunk_skipped += 1
            print()
            continue

        chunk_start = time.perf_counter()
        try:
            log.info(
                "Chunk started | doc={name} | id={id}",
                name=doc_name, id=doc_id,
            )

            if langchain_docs is not None:
                # Use the LangChain docs just produced by the parser (no file I/O)
                chunks, stats = chunker_service.chunk_langchain_documents(langchain_docs)
            else:
                # Load from the pre-existing parsed JSON on disk
                chunks, stats = chunker_service.chunk_by_document_id(
                    document_id=doc_id,
                    parsed_dir=PARSED_DIR,
                )

            chunk_elapsed = time.perf_counter() - chunk_start
            print(
                f"         Chunk: OK  | {stats.total_chunks:,} chunks "
                f"| avg={stats.avg_chunk_size:.0f} chars "
                f"| {format_duration(chunk_elapsed)}"
            )
            log.info(
                "Chunk complete | doc={name} | id={id} | chunks={n} | avg={avg:.1f}",
                name=doc_name, id=doc_id,
                n=stats.total_chunks, avg=stats.avg_chunk_size,
            )
            chunk_ok     += 1
            total_chunks += stats.total_chunks

        except (ChunkingError, Exception) as exc:
            chunk_elapsed = time.perf_counter() - chunk_start
            print(f"         Chunk: FAILED — {exc}")
            log.error(
                "Chunk failed | doc={name} | id={id} | error={error}",
                name=doc_name, id=doc_id, error=str(exc),
            )
            chunk_failed += 1
            failed_docs.append({
                "document_id": doc_id,
                "document_name": doc_name,
                "stage": "chunk",
                "error": str(exc),
            })

        print()

    # ── FINAL REPORT ──────────────────────────────────────────────────────────
    pipeline_elapsed = time.perf_counter() - pipeline_start

    print("=" * 70)
    print("  PIPELINE COMPLETE")
    print("=" * 70)
    print(f"  Total documents   : {total_docs}")
    print()
    print(f"  PARSING")
    print(f"    Success         : {parse_ok}")
    print(f"    Skipped         : {parse_skipped}")
    print(f"    Failed          : {parse_failed}")
    print()
    print(f"  CHUNKING")
    print(f"    Success         : {chunk_ok}")
    print(f"    Skipped         : {chunk_skipped}")
    print(f"    Failed          : {chunk_failed}")
    print(f"    Total Chunks    : {total_chunks:,}")
    print()
    print(f"  Total Duration    : {format_duration(pipeline_elapsed)}")
    print(f"  Completed At      : {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    if failed_docs:
        print("  FAILURES:")
        for fd in failed_docs:
            print(f"    [{fd['stage'].upper()}] {fd['document_name']} — {fd['error'][:80]}")
        print()

    print(f"  Output Dirs:")
    print(f"    Parsed  -> {PARSED_DIR}")
    print(f"    Chunks  -> {CHUNKS_DIR}")
    print("=" * 70)

    # Log final summary
    log.info(
        "Pipeline complete | docs={total} | parse_ok={p_ok} | parse_fail={p_fail} "
        "| chunk_ok={c_ok} | chunk_fail={c_fail} | total_chunks={chunks} | elapsed={elapsed}",
        total=total_docs,
        p_ok=parse_ok, p_fail=parse_failed,
        c_ok=chunk_ok, c_fail=chunk_failed,
        chunks=total_chunks,
        elapsed=format_duration(pipeline_elapsed),
    )


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="batch_parse_and_chunk",
        description=(
            "Batch pipeline: Parse all PDFs in documents.csv, "
            "then chunk each parsed document. "
            "Produces metadata/parsed/<id>.json and metadata/chunks/<id>_chunks.json."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full run — parse and chunk all 96 valid documents:
  .\\venv\\Scripts\\python.exe scripts/batch_parse_and_chunk.py

  # Resume — skip documents already parsed/chunked:
  .\\venv\\Scripts\\python.exe scripts/batch_parse_and_chunk.py --skip-parsed --skip-chunked

  # Only process Tax documents:
  .\\venv\\Scripts\\python.exe scripts/batch_parse_and_chunk.py --category Tax

  # Test run — first 3 documents only:
  .\\venv\\Scripts\\python.exe scripts/batch_parse_and_chunk.py --limit 3

  # Chunk-only (all parsing already done):
  .\\venv\\Scripts\\python.exe scripts/batch_parse_and_chunk.py --chunk-only --skip-chunked
""",
    )

    parser.add_argument(
        "--skip-parsed",
        action="store_true",
        default=False,
        help="Skip documents that already have a parsed JSON (resume mode).",
    )
    parser.add_argument(
        "--skip-chunked",
        action="store_true",
        default=False,
        help="Skip documents that already have a chunks JSON (resume mode).",
    )
    parser.add_argument(
        "--chunk-only",
        action="store_true",
        default=False,
        help="Skip parsing; only chunk documents that already have a parsed JSON.",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        choices=["Acts", "Tax", "CourtJudgement", "Legal_opinion"],
        help="Process only documents of this category.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N documents (useful for testing).",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        skip_parsed=args.skip_parsed,
        skip_chunked=args.skip_chunked,
        chunk_only=args.chunk_only,
        category=args.category,
        limit=args.limit,
    )
