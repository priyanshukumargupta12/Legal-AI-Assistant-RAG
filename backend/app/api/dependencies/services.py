"""
app/api/dependencies/services.py
================================
Service locator dependency injection factory methods.

PURPOSE:
    Centralizes creation and wiring of all backend domain services for FastAPI routes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.dataset.dataset_repository import FileSystemDatasetRepository
from app.dataset.dataset_service import DatasetService

from app.pdf_parser.parser_repository import FileSystemParserRepository
from app.pdf_parser.parser_service import PDFParserService

from app.chunking.chunk_repository import FileSystemChunkRepository
from app.chunking.chunk_service import ChunkingService

from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.qdrant_store import QdrantRepository

from app.elasticsearch.elastic_client import get_elasticsearch_client
from app.elasticsearch.elastic_repository import ElasticsearchRepository

from app.embeddings.embedder import BGEEmbedder
from app.embeddings.embedding_repository import FileSystemEmbeddingRepository, EmbeddingRepository
from app.embeddings.embedding_service import EmbeddingService


from app.retrieval.hybrid_ranker import WeightedRankFuser
from app.retrieval.retrieval_repository import HybridRetrievalRepository
from app.retrieval.retrieval_service import HybridRetrievalService

from app.llm.base_provider import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.groq_provider import GroqProvider
from app.llm.conversation_memory import ConversationHistoryMemory
from app.llm.llm_repository import ConversationHistoryRepository
from app.llm.llm_service import LLMService


# ── Config Dependency ──────────────────────────────────────────────────────────

SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── Dataset Dependency ─────────────────────────────────────────────────────────

def get_dataset_service(settings: SettingsDep) -> DatasetService:
    dataset_root = Path(settings.dataset_path).resolve()
    metadata_dir = Path(settings.metadata_path).resolve()
    repository = FileSystemDatasetRepository(metadata_dir=metadata_dir)
    return DatasetService(
        repository=repository,
        dataset_root=dataset_root,
        metadata_dir=metadata_dir,
    )


# ── PDF Parser Dependency ──────────────────────────────────────────────────────

def get_parser_service(settings: SettingsDep) -> PDFParserService:
    csv_path = Path(settings.metadata_path) / "documents.csv"
    output_dir = Path(settings.metadata_path) / "parsed"
    repository = FileSystemParserRepository()
    return PDFParserService(
        repository=repository,
        registry_csv_path=csv_path,
        output_dir=output_dir,
    )


# ── Chunking Dependency ────────────────────────────────────────────────────────

def get_chunking_service(settings: SettingsDep) -> ChunkingService:
    output_dir = Path(settings.metadata_path) / "chunks"
    repository = FileSystemChunkRepository()
    return ChunkingService(
        repository=repository,
        output_dir=output_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


# ── Embeddings / VectorStore Dependency ────────────────────────────────────────

def get_embedding_repository(settings: SettingsDep) -> EmbeddingRepository:
    metadata_dir = Path(settings.metadata_path).resolve()
    return FileSystemEmbeddingRepository(metadata_dir=metadata_dir)


def get_embedding_service(
    settings: SettingsDep,
    embedder: Annotated[BGEEmbedder, Depends(get_embedder)],
    repository: Annotated[EmbeddingRepository, Depends(get_embedding_repository)],
    vector_repo: Annotated[QdrantRepository, Depends(get_qdrant_repository)],
) -> EmbeddingService:
    return EmbeddingService(
        embedder=embedder,
        repository=repository,
        vector_repository=vector_repo,
    )


def get_qdrant_repository(
    settings: SettingsDep,
    request: Request,
) -> QdrantRepository:
    client = None
    if hasattr(request.app.state, "qdrant_client"):
        client = request.app.state.qdrant_client
    if not client:
        client = get_qdrant_client(settings)
    return QdrantRepository(client=client, settings=settings)


from app.elasticsearch.elastic_service import ElasticsearchService

# ── KeywordStore / Elasticsearch Dependency ────────────────────────────────────

def get_elasticsearch_repository(
    settings: SettingsDep,
    request: Request,
) -> ElasticsearchRepository:
    client = None
    if hasattr(request.app.state, "elasticsearch_client"):
        client = request.app.state.elasticsearch_client
    if not client:
        client = get_elasticsearch_client(settings)
    return ElasticsearchRepository(client=client, settings=settings)


def get_elasticsearch_service(
    settings: SettingsDep,
    repository: Annotated[ElasticsearchRepository, Depends(get_elasticsearch_repository)],
) -> ElasticsearchService:
    metadata_dir = Path(settings.metadata_path).resolve()
    return ElasticsearchService(
        repository=repository,
        metadata_dir=metadata_dir,
    )


# ── Embedder Dependency ────────────────────────────────────────────────────────

def get_embedder(settings: SettingsDep) -> BGEEmbedder:
    return BGEEmbedder(
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_cache_dir,
    )


# ── Retrieval Dependency ───────────────────────────────────────────────────────

def get_retrieval_service(
    settings: SettingsDep,
    vector_repo: Annotated[QdrantRepository, Depends(get_qdrant_repository)],
    keyword_repo: Annotated[ElasticsearchRepository, Depends(get_elasticsearch_repository)],
    embedder: Annotated[BGEEmbedder, Depends(get_embedder)],
) -> HybridRetrievalService:
    retrieval_repo = HybridRetrievalRepository(
        vector_repo=vector_repo,
        keyword_repo=keyword_repo,
        timeout_s=settings.retrieval_timeout_s,
    )
    fuser = WeightedRankFuser(
        vector_weight=settings.vector_weight,
        bm25_weight=settings.bm25_weight,
        rrf_k=settings.rrf_k,
    )
    return HybridRetrievalService(
        repository=retrieval_repo,
        embedder=embedder,
        fuser=fuser,
        retrieval_top_k=settings.retrieval_top_k,
        final_top_k=settings.retrieval_final_top_k,
        use_reranker=settings.use_reranker,
        rerank_model_name=settings.rerank_model_name,
        cache_dir=settings.embedding_cache_dir,
    )


# ── LLM Dependency ─────────────────────────────────────────────────────────────

def get_llm_provider(settings: SettingsDep) -> LLMProvider:
    provider_name = settings.llm_provider.lower()
    if provider_name == "gemini":
        return GeminiProvider(settings)
    elif provider_name == "openai":
        return OpenAIProvider(settings)
    elif provider_name == "groq":
        return GroqProvider(settings)
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def get_llm_service(
    settings: SettingsDep,
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> LLMService:
    repo = ConversationHistoryRepository(settings)
    # Using a simple singleton runtime window
    from app.llm.llm_controller import get_conversation_memory
    memory = get_conversation_memory()
    return LLMService(
        provider=provider,
        repository=repo,
        memory=memory,
        settings=settings,
    )


# ── Evaluation Dependency ───────────────────────────────────────────────────────

from app.evaluation.evaluation_service import EvaluationService


def get_evaluation_service(
    settings: SettingsDep,
    retrieval_service: Annotated[HybridRetrievalService, Depends(get_retrieval_service)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
) -> EvaluationService:
    return EvaluationService(
        settings=settings,
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )


# ── Graph RAG Dependency ────────────────────────────────────────────────────────

from app.graph_rag.graph_repository import GraphRepository
from app.graph_rag.graph_service import GraphService


def get_graph_service(settings: SettingsDep) -> GraphService:
    """
    Construct and return a GraphService instance.

    GraphService automatically attempts to load a persisted graph from disk
    on initialization. If no graph exists yet, it starts empty and waits for
    a POST /api/v1/graph-rag/build call.

    Args:
        settings: Application settings (injected by FastAPI DI).

    Returns:
        Initialized GraphService instance.
    """
    storage_dir = Path(settings.metadata_path) / "graph"
    chunks_dir = Path(settings.metadata_path) / "chunks"
    repository = GraphRepository(storage_dir=storage_dir)
    return GraphService(
        repository=repository,
        chunks_dir=chunks_dir,
        min_edge_confidence=getattr(settings, "graph_min_edge_confidence", 0.3),
    )


# ── OKF Knowledge Dependency ──────────────────────────────────────────────────

from app.knowledge.knowledge_repository import KnowledgeRepository
from app.knowledge.knowledge_service import KnowledgeService


def get_knowledge_service(settings: SettingsDep) -> KnowledgeService:
    """
    Construct and return a KnowledgeService instance.

    KnowledgeService automatically attempts to load persisted OKF documents/chunks
    from disk on initialization.

    Args:
        settings: Application settings (injected by FastAPI DI).

    Returns:
        Initialized KnowledgeService instance.
    """
    storage_dir = Path(settings.metadata_path) / "knowledge"
    chunks_dir = Path(settings.metadata_path) / "chunks"
    repository = KnowledgeRepository(storage_dir=storage_dir, chunks_dir=chunks_dir)
    return KnowledgeService(
        repository=repository,
        top_n_keywords=getattr(settings, "knowledge_top_keywords", 15),
        doc_top_keywords=getattr(settings, "knowledge_doc_top_keywords", 20),
        max_entities=getattr(settings, "knowledge_max_entities", 30),
        min_relation_conf=getattr(settings, "knowledge_min_relation_conf", 0.4),
    )

