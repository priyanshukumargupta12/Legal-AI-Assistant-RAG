"""
app/elasticsearch/__init__.py
===============================
Public interface for the Elasticsearch module.

Exports the key objects that other modules need to import:
    - get_elasticsearch_client  — client factory
    - ElasticsearchRepository   — concrete keyword repository
    - ElasticsearchService      — orchestration service
    - router                    — FastAPI APIRouter for API registration
"""

from app.elasticsearch.elastic_client import get_elasticsearch_client
from app.elasticsearch.elastic_repository import ElasticsearchRepository
from app.elasticsearch.elastic_service import ElasticsearchService
from app.elasticsearch.elastic_controller import router as elasticsearch_router

__all__ = [
    "get_elasticsearch_client",
    "ElasticsearchRepository",
    "ElasticsearchService",
    "elasticsearch_router",
]
