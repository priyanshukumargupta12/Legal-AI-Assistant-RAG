"""
app/vectorstore/payload_builder.py
==================================
Utility to build vector payloads for Qdrant storage.

PURPOSE:
    Constructs standardized payload dictionaries from DocumentChunk entities
    to satisfy database and retrieval schema contracts.
"""

from __future__ import annotations

from typing import Any, Dict
from app.models.document import DocumentChunk


class PayloadBuilder:
    """
    Constructs compliant payloads for Qdrant indexing.
    """

    @staticmethod
    def build_payload(chunk: DocumentChunk) -> Dict[str, Any]:
        """
        Build a dictionary of payload key-values matching the specification.

        Args:
            chunk: The DocumentChunk domain object.

        Returns:
            Dict containing standardized keys and values.
        """
        return {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "document_name": chunk.document_name,
            "category": chunk.category,
            "page_number": chunk.page_number,
            "chunk_text": chunk.text,
            "source": chunk.source,
            "metadata": chunk.metadata,
        }
