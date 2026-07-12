"""
core/database/elasticsearch_client.py
=======================================
Elasticsearch async client factory and connection management.

PURPOSE:
    Creates and caches the AsyncElasticsearch client instance.
    Provides a single get_elasticsearch_client() for dependency injection.

SOLID: Single Responsibility — ES connection management only.
"""

from __future__ import annotations

# TODO: Implement in Milestone 6 (Elasticsearch BM25)
# from elasticsearch import AsyncElasticsearch


def get_elasticsearch_client():
    """
    Factory function that returns a configured AsyncElasticsearch client.

    Returns:
        AsyncElasticsearch: Configured ES client instance.

    Raises:
        KeywordStoreConnectionError: If connection cannot be established.
    """
    # TODO: Implement in Milestone 6
    ...
