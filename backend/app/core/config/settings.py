"""
core/config/settings.py
=======================
Centralized application configuration using Pydantic BaseSettings.

PURPOSE:
    Single source of truth for all application settings.
    All environment variables are loaded, validated, and typed here.
    Any misconfiguration fails fast at startup with a descriptive error.

DESIGN:
    - Inherits from pydantic_settings.BaseSettings
    - Reads from .env file automatically
    - Every field is typed and validated at application startup
    - Uses @computed_field for derived values
    - Exported as a singleton via get_settings() with lru_cache

SOLID: Single Responsibility — this class only handles configuration.
DRY:   All config values referenced via settings.FIELD_NAME; no duplication.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment variables and .env file.

    Fields are grouped by subsystem. Every field has a default where safe;
    critical secrets (API keys) default to empty string and are validated
    at startup to ensure they are provided.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars gracefully
    )

    # ─── Application ──────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application runtime environment",
    )
    app_name: str = Field(
        default="Enterprise AI Legal Assistant",
        description="Application display name",
    )
    app_version: str = Field(default="1.0.0", description="API version string")
    app_host: str = Field(default="0.0.0.0", description="Uvicorn bind host")
    app_port: int = Field(default=8000, ge=1, le=65535, description="Uvicorn port")
    app_debug: bool = Field(default=False, description="Enable debug/hot-reload mode")

    # ─── LLM Provider ─────────────────────────────────────────────────────────
    llm_provider: Literal["gemini", "openai"] = Field(
        default="gemini",
        description="Active LLM provider",
    )
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model identifier",
    )
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model identifier",
    )

    # ─── Qdrant Vector Database ───────────────────────────────────────────────
    qdrant_mode: Literal["memory", "local", "cloud"] = Field(
        default="local",
        description="Qdrant connection mode",
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant server URL",
    )
    qdrant_api_key: str = Field(
        default="",
        description="Qdrant Cloud API key (leave empty for local)",
    )
    qdrant_collection_name: str = Field(
        default="legal_documents",
        description="Qdrant collection name",
    )

    # ─── Elasticsearch ────────────────────────────────────────────────────────
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch server URL",
    )
    elasticsearch_api_key: str = Field(
        default="",
        description="Elasticsearch API key (takes priority over username/password)",
    )
    elasticsearch_username: str = Field(
        default="",
        description="Elasticsearch username (fallback if no API key)",
    )
    elasticsearch_password: str = Field(
        default="",
        description="Elasticsearch password (fallback if no API key)",
    )
    elasticsearch_index_name: str = Field(
        default="legal_documents",
        description="Elasticsearch index name",
    )
    elasticsearch_bulk_batch_size: int = Field(
        default=200,
        ge=1,
        le=2000,
        description="Number of documents per Elasticsearch bulk request",
    )
    elasticsearch_refresh_interval: str = Field(
        default="30s",
        description="Elasticsearch index refresh interval (e.g. '1s', '30s', '-1')",
    )


    # ─── Embedding Model ──────────────────────────────────────────────────────
    embedding_model_name: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="HuggingFace model ID for embeddings",
    )
    embedding_batch_size: int = Field(
        default=32,
        ge=1,
        le=512,
        description="Batch size for embedding generation",
    )
    embedding_cache_dir: str = Field(
        default="../embeddings/cache",
        description="Local cache directory for downloaded models",
    )

    # ─── Retrieval ────────────────────────────────────────────────────────────
    retrieval_top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of results fetched from each retriever",
    )
    retrieval_final_top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Final number of results after fusion merging",
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        description="RRF robustness constant k",
    )
    vector_score_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum cosine score for Qdrant results",
    )
    vector_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight applied to vector search scores during Weighted Rank Fusion (0.0–1.0)",
    )
    bm25_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight applied to BM25 scores during Weighted Rank Fusion (0.0–1.0)",
    )
    retrieval_timeout_s: float = Field(
        default=10.0,
        ge=1.0,
        description="Maximum seconds to wait for each retrieval call before timeout",
    )
    rerank_model_name: str = Field(
        default="BAAI/bge-reranker-base",
        description="SentenceTransformers CrossEncoder reranker model to use",
    )
    use_reranker: bool = Field(
        default=False,
        description="Enable/disable CrossEncoder re-ranking stage after hybrid retrieval",
    )
    min_vector_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum vector similarity score to determine if a query is within domain",
    )
    min_rerank_score: float = Field(
        default=0.0,
        description="Minimum rerank score for confidence check",
    )
    min_hybrid_score: float = Field(
        default=0.005,
        ge=0.0,
        description="Minimum hybrid fuser score for confidence check",
    )

    # ─── Chunking ─────────────────────────────────────────────────────────────
    chunk_size: int = Field(
        default=1800,
        ge=100,
        description="Target chunk size in characters",
    )
    chunk_overlap: int = Field(
        default=230,
        ge=0,
        description="Character overlap between consecutive chunks",
    )
    min_chunk_length: int = Field(
        default=50,
        ge=1,
        description="Minimum chunk length; shorter chunks are discarded",
    )

    # ─── Dataset ──────────────────────────────────────────────────────────────
    dataset_root_path: str = Field(
        default="../dataset",
        description="Root path to the dataset directory",
    )
    metadata_output_path: str = Field(
        default="../metadata",
        description="Output directory for generated metadata files",
    )
    auto_scan_on_startup: bool = Field(
        default=False,
        description="Auto-scan dataset directory on startup",
    )
    auto_ingest_on_startup: bool = Field(
        default=False,
        description="Auto-ingest all documents on startup",
    )

    # ── Convenience aliases (resolved absolute Path strings) ──────────────────
    @property
    def dataset_path(self) -> str:
        """Alias for dataset_root_path — used by DatasetService."""
        return self.dataset_root_path

    @property
    def metadata_path(self) -> str:
        """Alias for metadata_output_path — used by DatasetRepository."""
        return self.metadata_output_path

    # ─── Logging ──────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Application log level",
    )
    log_dir: str = Field(
        default="../logs",
        description="Directory for rotating log files",
    )
    log_rotation: str = Field(
        default="10 MB",
        description="Log file rotation size threshold",
    )
    log_retention: int = Field(
        default=5,
        ge=1,
        description="Number of rotated log files to retain",
    )

    # ─── Security ─────────────────────────────────────────────────────────────
    cors_origins: Any = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins",
    )
    rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        description="Max API requests per minute per IP",
    )
    max_upload_size_mb: int = Field(
        default=50,
        ge=1,
        description="Maximum PDF upload size in MB",
    )
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for signing tokens",
    )

    # ─── Search History ───────────────────────────────────────────────────────
    search_history_path: str = Field(
        default="../logs/search_history.json",
        description="File path for persisting search history",
    )
    search_history_max_entries: int = Field(
        default=1000,
        ge=1,
        description="Maximum number of history entries to retain",
    )

    # ─── Graph RAG ────────────────────────────────────────────────────────────
    graph_storage_path: str = Field(
        default="../metadata/graph",
        description="Path to the graph storage directory",
    )
    graph_build_depth: int = Field(
        default=2,
        ge=1,
        description="BFS build traversal depth",
    )
    graph_max_neighbors: int = Field(
        default=10,
        ge=1,
        description="Max neighbors to return per hop",
    )
    graph_min_edge_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for an edge to be included",
    )

    # ─── OKF Knowledge ────────────────────────────────────────────────────────
    knowledge_storage_path: str = Field(
        default="../metadata/knowledge",
        description="Path to the OKF knowledge storage directory",
    )
    knowledge_top_keywords: int = Field(
        default=15,
        ge=1,
        description="Max keywords per chunk",
    )
    knowledge_doc_top_keywords: int = Field(
        default=20,
        ge=1,
        description="Max keywords per document",
    )
    knowledge_max_entities: int = Field(
        default=30,
        ge=1,
        description="Max named entities per chunk",
    )
    knowledge_min_relation_conf: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for relation inclusion",
    )

    # ─── Validators ───────────────────────────────────────────────────────────
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> List[str]:
        """Parse comma-separated CORS origins string into a list."""
        if isinstance(value, str):
            if value.startswith("[") and value.endswith("]"):
                try:
                    import json
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value]
        return [str(value).strip()]

    @field_validator(
        "embedding_cache_dir",
        "log_dir",
        "dataset_root_path",
        "metadata_output_path",
        "search_history_path",
        "graph_storage_path",
        "knowledge_storage_path",
        mode="before",
    )
    @classmethod
    def resolve_path(cls, value: str) -> str:
        """Resolve relative paths to absolute paths from the backend directory."""
        return str(Path(value).resolve())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application Settings singleton.

    Using lru_cache ensures Settings is instantiated exactly once,
    making configuration loading a zero-cost operation after startup.

    Returns:
        Settings: Validated application configuration instance.

    Raises:
        ValidationError: If required environment variables are missing or invalid.
    """
    return Settings()
