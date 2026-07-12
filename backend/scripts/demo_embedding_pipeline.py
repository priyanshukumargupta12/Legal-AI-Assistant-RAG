"""
scripts/demo_embedding_pipeline.py
==================================
Demonstration of the Embedding Pipeline and Qdrant integration.

PURPOSE:
    Demonstrates:
        1. How to initialize Qdrant (in-memory mode for easy testing).
        2. How to create a collection with the proper configuration.
        3. How to load and validate a sample chunk.
        4. How to generate an L2-normalized embedding vector using BGE-small.
        5. How to store the chunk vector and payload inside Qdrant.
        6. How to retrieve the chunk back via vector search.

USAGE:
    Run from the backend directory:
        python scripts/demo_embedding_pipeline.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure backend root is on the Python path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.embeddings.embedder import BGEEmbedder
from app.embeddings.embedding_models import EmbeddingStatistics
from app.embeddings.embedding_repository import FileSystemEmbeddingRepository
from app.embeddings.embedding_utils import validate_chunk_metadata, validate_embedding_dimension
from app.models.document import DocumentChunk
from app.vectorstore import CollectionManager, get_qdrant_client, QdrantRepository


async def main() -> None:
    print("=" * 80)
    print("         EMBEDDING PIPELINE & QDRANT DEMONSTRATION")
    print("=" * 80)

    # 1. Load Settings and configure for in-memory Qdrant
    print("\n[Step 1] Loading configurations...")
    settings = get_settings()
    
    # Override settings to run Qdrant in memory for this demo
    settings.qdrant_mode = "memory"
    settings.qdrant_collection_name = "demo_legal_documents"
    
    print(f"  * Mode: {settings.qdrant_mode}")
    print(f"  * Collection: {settings.qdrant_collection_name}")
    print(f"  * Embedding Model: {settings.embedding_model_name}")

    # 2. Initialize Qdrant Client
    print("\n[Step 2] Initializing Qdrant Client (in-memory)...")
    qdrant_client = get_qdrant_client(settings)
    print("  * Qdrant client initialized.")

    # 3. Manage/Create collection
    print("\n[Step 3] Creating collection automatically...")
    # CollectionManager creates collection with Cosine distance metric and 384 dimensions
    CollectionManager.create_collection_if_not_exists(
        client=qdrant_client,
        collection_name=settings.qdrant_collection_name,
        dimension=384,
    )
    
    # Initialize the repository wrapper
    vector_repo = QdrantRepository(client=qdrant_client, settings=settings)

    # 4. Initialize BGE Embedding Model
    print("\n[Step 4] Pre-loading BGE-small-en-v1.5 embedding model...")
    t0 = time.perf_counter()
    embedder = BGEEmbedder(
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_cache_dir,
    )
    t_load = time.perf_counter() - t0
    print(f"  * Model loaded in {t_load:.2f} seconds.")

    # 5. Define a sample chunk
    print("\n[Step 5] Creating a sample legal document chunk...")
    sample_raw_chunk = {
        "chunk_id": "demo_chunk_001",
        "document_id": "00000000-0000-0000-0000-000000000001",
        "document_name": "Demo_Tax_Act_2026.pdf",
        "page": 1,
        "category": "Tax",
        "chunk_index": 0,
        "text": (
            "Section 401. Short Term Delinquent Filing Interest. "
            "Any taxpayer who fails to submit tax filings on or before the due date "
            "shall be assessed a late fee of 5% of the total tax liability per month, "
            "up to a maximum of 25%. Interest on unpaid balances shall accumulate "
            "at the federal short-term rate plus 3 percentage points."
        ),
        "file_path": "dataset/Tax/Demo_Tax_Act_2026.pdf",
        "source": "Demo_Tax_Act_2026.pdf",
        "metadata": {
            "document_id": "00000000-0000-0000-0000-000000000001",
            "document_name": "Demo_Tax_Act_2026.pdf",
            "category": "Tax",
            "page_number": 1,
            "file_path": "dataset/Tax/Demo_Tax_Act_2026.pdf",
            "source": "Demo_Tax_Act_2026.pdf"
        }
    }

    # 6. Validate Chunk
    print("\n[Step 6] Validating sample chunk...")
    errors = validate_chunk_metadata(sample_raw_chunk)
    if errors:
        print(f"  [ERROR] Validation failed: {errors}")
        return
    print("  * Chunk is valid.")

    chunk = DocumentChunk(
        chunk_id=sample_raw_chunk["chunk_id"],
        document_id=sample_raw_chunk["document_id"],
        document_name=sample_raw_chunk["document_name"],
        category=sample_raw_chunk["category"],
        page_number=sample_raw_chunk["page"],
        chunk_index=sample_raw_chunk["chunk_index"],
        text=sample_raw_chunk["text"],
        char_count=len(sample_raw_chunk["text"]),
        source=sample_raw_chunk["source"],
        metadata=sample_raw_chunk["metadata"],
    )

    # 7. Generate Embedding Vector
    print("\n[Step 7] Generating dense vector embedding (BAAI/bge-small-en-v1.5)...")
    t0 = time.perf_counter()
    # Documents are embedded without instruction prefix
    embeddings = embedder.embed_documents([chunk.text])
    vector = embeddings[0]
    t_embed = time.perf_counter() - t0
    
    print(f"  * Embedding generated in {t_embed*1000:.1f} ms.")
    print(f"  * Vector Dimension: {len(vector)}")
    
    # Validate dimensions
    if not validate_embedding_dimension(vector, 384):
        print("  [ERROR] Invalid vector dimension generated!")
        return
    print("  * Vector dimension is valid (384 dimensions).")

    # 8. Store Vector and Payload in Qdrant
    print("\n[Step 8] Storing vector and metadata payload in Qdrant...")
    await vector_repo.upsert_chunks(
        chunks=[chunk],
        embeddings=[vector],
    )
    print("  * Chunk successfully stored in Qdrant.")

    # 9. Perform Vector Search (Verify Retrievability)
    print("\n[Step 9] Performing test vector search...")
    query_text = "What is the penalty for filing late taxes?"
    print(f"  * User Query: '{query_text}'")
    
    # Search queries require prepended instruction prefix
    query_vector = embedder.embed_query(query_text)
    print(f"  * Query vector generated (Instruction prefix prepended automatically).")

    results = await vector_repo.search(
        query_vector=query_vector,
        top_k=1,
    )
    
    if not results:
        print("  [ERROR] No search results returned!")
        return

    retrieved = results[0]
    print(f"  * Found Match! Score: {retrieved.score:.4f} (Rank {retrieved.rank})")
    print(f"  * Retrieved Chunk Text:")
    print(f"    \"{retrieved.text}\"")
    print(f"  * Citation: {retrieved.document_name} | Page {retrieved.page_number} | Category: {retrieved.category}")

    # 10. Write Statistics
    print("\n[Step 10] Writing Pipeline run statistics...")
    stats = EmbeddingStatistics(
        total_chunks=1,
        embedded_chunks=1,
        failed_chunks=0,
        average_embedding_time=t_embed,
        embedding_dimension=384,
    )
    
    file_repo = FileSystemEmbeddingRepository(metadata_dir=Path(settings.metadata_path))
    stats_file = file_repo.save_embedding_statistics(stats)
    
    print(f"  * Stats written to: {stats_file}")
    with open(stats_file, "r") as f:
        print(json.dumps(json.load(f), indent=4))

    print("\n" + "=" * 80)
    print("         EMBEDDING PIPELINE DEMONSTRATION COMPLETE SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
