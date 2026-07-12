"""
app/vectorstore/qdrant_client.py
================================
Qdrant client initialization and factory.

PURPOSE:
    Provides a configured QdrantClient instance based on settings.
    Handles 'memory', 'local', and 'cloud' modes.
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from app.core.config import Settings
from app.core.exceptions import VectorStoreConnectionError
from app.vectorstore.vector_logger import vector_log


def get_qdrant_client(settings: Settings) -> QdrantClient:
    """
    Initialize and return a QdrantClient instance based on active settings.

    Args:
        settings: Application Settings.

    Returns:
        Configured QdrantClient.

    Raises:
        VectorStoreConnectionError: If connection setup fails.
    """
    mode = settings.qdrant_mode
    url = settings.qdrant_url
    api_key = settings.qdrant_api_key

    vector_log.info(
        "Initializing Qdrant client | mode={mode} | url={url}",
        mode=mode,
        url=url if mode != "memory" else ":memory:",
    )

    try:
        if mode == "memory":
            return QdrantClient(":memory:")
        elif mode == "local":
            return QdrantClient(url=url, timeout=60.0)
        elif mode == "cloud":
            if not url or url.startswith("<YOUR"):
                raise ValueError("Valid QDRANT_URL is required for cloud mode.")
            if not api_key or api_key.startswith("<YOUR"):
                raise ValueError("Valid QDRANT_API_KEY is required for cloud mode.")
            return QdrantClient(url=url, api_key=api_key, timeout=60.0)
        else:
            raise ValueError(f"Unknown QDRANT_MODE: {mode}")
    except Exception as exc:
        vector_log.error(
            "Failed to connect to Qdrant | mode={mode} | url={url} | error={error}",
            mode=mode,
            url=url,
            error=str(exc),
        )
        raise VectorStoreConnectionError(url=url) from exc
