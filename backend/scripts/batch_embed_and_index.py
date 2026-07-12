"""
scripts/batch_embed_and_index.py
================================
Batch Ingestion: Generate embeddings and index all chunked documents in Qdrant.

PURPOSE:
    Scans the metadata/chunks/ folder for all chunked JSON files,
    loads the chunks for each document, validates them, encodes them
    in batches using the BGE model, and upserts them to the configured Qdrant collection.

USAGE:
    From the backend directory:
        python scripts/batch_embed_and_index.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend root is on the Python path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.embeddings.embedder import BGEEmbedder
from app.embeddings.embedding_repository import FileSystemEmbeddingRepository
from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.embedding_models import EmbeddingStatistics
from app.vectorstore import get_qdrant_client, QdrantRepository


async def run_batch_ingestion() -> None:
    settings = get_settings()
    chunks_dir = Path(settings.metadata_path) / "chunks"

    print("=" * 80)
    print("         BATCH EMBEDDING AND QDRANT INGESTION PIPELINE")
    print("=" * 80)
    print(f"  * Qdrant Mode    : {settings.qdrant_mode}")
    print(f"  * Qdrant URL     : {settings.qdrant_url if settings.qdrant_mode != 'memory' else 'N/A'}")
    print(f"  * Collection Name: {settings.qdrant_collection_name}")
    print(f"  * Embedding Model: {settings.embedding_model_name}")
    print(f"  * Batch Size     : {settings.embedding_batch_size}")
    print(f"  * Chunks Dir     : {chunks_dir}")
    print("=" * 80)

    # 1. Discover all chunk files
    if not chunks_dir.exists():
        print(f"[ERROR] Chunks directory not found at: {chunks_dir}. Run chunker first.")
        sys.exit(1)

    chunk_files = list(chunks_dir.glob("*_chunks.json"))
    total_docs = len(chunk_files)

    if total_docs == 0:
        print(f"[WARNING] No chunk JSON files found in {chunks_dir}.")
        return

    print(f"\nDiscovered {total_docs} document chunk files to process.")

    # 2. Initialize Services
    print("\nInitializing embedding services...")
    qdrant_client = get_qdrant_client(settings)
    vector_repository = QdrantRepository(client=qdrant_client, settings=settings)
    
    embedder = BGEEmbedder(
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_cache_dir,
    )
    
    repository = FileSystemEmbeddingRepository(metadata_dir=Path(settings.metadata_path))
    
    service = EmbeddingService(
        embedder=embedder,
        repository=repository,
        vector_repository=vector_repository,
    )

    # 3. Process each file
    total_chunks_processed = 0
    total_chunks_indexed = 0
    total_chunks_failed = 0
    
    start_time = time.perf_counter()
    print("\nStarting batch ingestion...\n")

    for idx, chunk_file in enumerate(chunk_files, start=1):
        # File format: <document_id>_chunks.json
        doc_id = chunk_file.name.replace("_chunks.json", "")
        doc_name = ""
        
        # Read the file header to get the human-readable document name
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "metadata" in data:
                    doc_name = data["metadata"].get("document_name", "")
        except Exception:
            pass

        if not doc_name:
            doc_name = doc_id

        print(f"[{idx:3d}/{total_docs}] Ingesting: {doc_name}")
        t0 = time.perf_counter()
        
        try:
            stats = await service.embed_document(
                document_id=doc_id,
                batch_size=settings.embedding_batch_size,
            )
            elapsed = time.perf_counter() - t0
            
            total_chunks_processed += stats.total_chunks
            total_chunks_indexed += stats.embedded_chunks
            total_chunks_failed += stats.failed_chunks
            
            print(
                f"      Success | Chunks: {stats.total_chunks} "
                f"| Embedded: {stats.embedded_chunks} "
                f"| Failed: {stats.failed_chunks} "
                f"| Time: {elapsed:.2f}s"
            )
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"      [FAILED] Ingestion error: {exc} | Time: {elapsed:.2f}s")
            total_chunks_failed += 1

    # 4. Final Aggregated Run Summary
    total_duration = time.perf_counter() - start_time
    avg_chunk_time = (total_duration / total_chunks_processed) if total_chunks_processed > 0 else 0.0

    aggregated_stats = EmbeddingStatistics(
        total_chunks=total_chunks_processed,
        embedded_chunks=total_chunks_indexed,
        failed_chunks=total_chunks_failed,
        average_embedding_time=avg_chunk_time,
        embedding_dimension=384,
        processed_at=datetime.now(timezone.utc),
    )

    # Save final summary stats
    repository.save_embedding_statistics(aggregated_stats)

    print("\n" + "=" * 80)
    print("         BATCH INGESTION RUN COMPLETE")
    print("=" * 80)
    print(f"  Documents processed    : {total_docs}")
    print(f"  Total chunks attempted : {total_chunks_processed:,}")
    print(f"  Total chunks indexed   : {total_chunks_indexed:,}")
    print(f"  Total chunks failed    : {total_chunks_failed:,}")
    print(f"  Total duration         : {total_duration/60:.2f} minutes ({total_duration:.1f}s)")
    print(f"  Grand average per chunk: {avg_chunk_time*1000:.1f} ms")
    print(f"  Statistics saved to    : {Path(settings.metadata_path) / 'embedding_statistics.json'}")
    print("=" * 80)


if __name__ == "__main__":
    import json
    asyncio.run(run_batch_ingestion())
