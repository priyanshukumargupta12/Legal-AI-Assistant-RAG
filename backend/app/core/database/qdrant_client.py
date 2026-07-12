"""
core/database/qdrant_client.py
================================
Qdrant client factory and connection management.

PURPOSE:
    Creates and caches the Qdrant client instance based on QDRANT_MODE.
    Provides a single get_qdrant_client() function for dependency injection.

MODES:
    memory → QdrantClient("":memory:"") — development/demo
    local  → QdrantClient(url) — local server
    cloud  → QdrantClient(url, api_key) — Qdrant Cloud

SOLID: Single Responsibility — Qdrant connection management only.
"""

from __future__ import annotations

# TODO: Implement in Milestone 5 (Qdrant Vector Store)
# from qdrant_client import QdrantClient


def get_qdrant_client():
    """
    Factory function that returns the appropriate Qdrant client
    based on QDRANT_MODE setting.

    Returns:
        QdrantClient: Configured Qdrant client instance.

    Raises:
        VectorStoreConnectionError: If connection cannot be established.
    """
    # TODO: Implement in Milestone 5
    ...
