"""
app/embeddings/embedding_models.py
==================================
Pure Python domain models for the Embedding Module.

PURPOSE:
    Defines immutable, strongly-typed domain entities used throughout the
    embedding pipeline. These models are independent of database or
    framework code to maximize portability and testability.

ENTITIES:
    DocumentEmbedding   — Holds the generated vector and references for a chunk.
    EmbeddingStatistics — Aggregate statistics computed after embedding run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class DocumentEmbedding:
    """
    Immutable representation of a generated text embedding vector for a chunk.

    Attributes:
        chunk_id:      Globally unique identifier of the source chunk.
        document_id:   Parent document UUID.
        embedding:     L2-normalized dense float32 vector (384 dimensions).
    """

    chunk_id: str
    document_id: str
    embedding: List[float]


@dataclass
class EmbeddingStatistics:
    """
    Aggregate statistics generated at the end of an embedding pipeline run.

    Attributes:
        total_chunks:           Number of chunks loaded/attempted.
        embedded_chunks:        Number of chunks successfully embedded.
        failed_chunks:          Number of chunks that failed validation or embedding.
        average_embedding_time: Average time taken per chunk embedding in seconds.
        embedding_dimension:    Size of the generated vector space (default 384).
        processed_at:           UTC timestamp when the pipeline finished.
    """

    total_chunks: int
    embedded_chunks: int
    failed_chunks: int
    average_embedding_time: float
    embedding_dimension: int = 384
    processed_at: datetime = field(default_factory=datetime.utcnow)
