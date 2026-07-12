"""
app/embeddings/embedding_schemas.py
===================================
Pydantic v2 schemas for the Embedding Module.

PURPOSE:
    Defines validated data structures for the embedding inputs/outputs
    at API boundaries. Separates wire-format from internal domain entities.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class EmbeddingStatisticsSchema(BaseModel):
    """
    Validation schema summarizing an embedding pipeline run.
    """

    total_chunks: int = Field(
        ...,
        description="Total number of chunks loaded/attempted.",
    )
    embedded_chunks: int = Field(
        ...,
        description="Total number of chunks successfully embedded and stored.",
    )
    failed_chunks: int = Field(
        ...,
        description="Total number of chunks that failed validation or embedding.",
    )
    average_embedding_time: float = Field(
        ...,
        description="Average execution time per chunk embedding (seconds).",
    )
    embedding_dimension: int = Field(
        384,
        description="Dimensionality of the dense vectors generated.",
    )
    processed_at: datetime = Field(
        ...,
        description="UTC timestamp when the run was completed.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_chunks": 120,
                "embedded_chunks": 120,
                "failed_chunks": 0,
                "average_embedding_time": 0.005,
                "embedding_dimension": 384,
                "processed_at": "2026-07-11T12:00:00Z",
            }
        }
    }


class EmbeddingRequestSchema(BaseModel):
    """
    Schema for embedding requests.
    """

    document_ids: List[str] = Field(
        ...,
        description="List of document UUIDs to process from metadata store.",
    )


class EmbeddingResponseSchema(BaseModel):
    """
    Response schema returned by the embedding controller.
    """

    status: str = Field(..., description="Run status (success | failed).")
    statistics: EmbeddingStatisticsSchema = Field(
        ...,
        description="Aggregated run execution statistics.",
    )
    message: str = Field(..., description="Detail message about execution.")
