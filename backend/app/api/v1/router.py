"""
api/v1/router.py
================
Root API v1 router that aggregates all feature routers.

PURPOSE:
    Single aggregation point for all /api/v1/* routes.
    Imported by main.py and mounted under API_V1_PREFIX.
    Each feature has its own sub-router included here.

SOLID: Single Responsibility — router aggregation only.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    dataset,
    parser,
    chunking,
    embeddings,
    elasticsearch,
    retrieval,
    llm,
    evaluation,
    golden,
    graph_rag,
    knowledge,
)

api_router = APIRouter()

api_router.include_router(dataset.router, tags=["Dataset Management"])
api_router.include_router(parser.router, tags=["PDF Parsing"])
api_router.include_router(chunking.router, tags=["Intelligent Chunking"])
api_router.include_router(embeddings.router, tags=["Dense Embeddings"])
api_router.include_router(elasticsearch.router, tags=["Elasticsearch Indexing"])
api_router.include_router(retrieval.router, tags=["Hybrid Retrieval"])
api_router.include_router(llm.router, tags=["LLM Assistant"])
api_router.include_router(evaluation.router, tags=["Golden Set Evaluation"])
api_router.include_router(golden.router, tags=["Golden Set Management"])
api_router.include_router(graph_rag.router, tags=["Graph RAG"])
api_router.include_router(knowledge.router, tags=["OKF Knowledge"])


