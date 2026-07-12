"""
app/retrieval/__init__.py
===========================
Public interface for the Hybrid Retrieval module.

Exports the key objects other modules need:
    - HybridRetriever           — convenience facade
    - HybridRetrievalService    — orchestration service
    - HybridRetrievalRepository — data-access layer
    - WeightedRankFuser         — WRF algorithm
    - RRFRanker                 — alternative RRF algorithm
    - router                    — FastAPI APIRouter for registration
"""

from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.retrieval_service import HybridRetrievalService
from app.retrieval.retrieval_repository import HybridRetrievalRepository
from app.retrieval.hybrid_ranker import WeightedRankFuser
from app.retrieval.rrf_ranker import RRFRanker
from app.retrieval.retrieval_controller import router as retrieval_router

__all__ = [
    "HybridRetriever",
    "HybridRetrievalService",
    "HybridRetrievalRepository",
    "WeightedRankFuser",
    "RRFRanker",
    "retrieval_router",
]
