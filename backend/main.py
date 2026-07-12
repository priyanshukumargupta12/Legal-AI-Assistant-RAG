"""
main.py
# Trigger reload - Enabled CrossEncoder Reranking and larger chunk size
========
FastAPI application factory and entry point.

PURPOSE:
    Creates and configures the FastAPI application instance.
    Registers all routers, middleware, and exception handlers.
    Manages application lifespan (startup/shutdown) events.

STARTUP SEQUENCE:
    1. Configure logging (6 Loguru sinks)
    2. Validate all settings (Pydantic BaseSettings)
    3. Connect to Qdrant (create collection if not exists)
    4. Connect to Elasticsearch (create index if not exists)
    5. Load BGE embedding model
    6. Optionally scan/ingest dataset (if AUTO_* settings are True)
    7. Register all routers under /api/v1

SHUTDOWN:
    1. Close Qdrant client connection
    2. Close Elasticsearch client connection

SOLID: Single Responsibility — application wiring and configuration only.
       No business logic in this file.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.constants import API_V1_PREFIX
from app.core.exceptions import LegalAssistantError
from app.logging.logger import configure_logging, get_logger

# ─── Settings singleton ────────────────────────────────────────────────────────
settings = get_settings()

# ─── Application logger ────────────────────────────────────────────────────────
log = get_logger("app")


# =============================================================================
# LIFESPAN — Startup / Shutdown
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles all startup initialization and graceful shutdown cleanup.
    Called automatically by FastAPI when the application starts and stops.
    """
    # ── STARTUP ───────────────────────────────────────────────────────────────
    log.info("Starting {name} v{version}", name=settings.app_name, version=settings.app_version)
    log.info("Environment: {env}", env=settings.app_env)

    # Copy pre-packaged metadata to writable directory if running on Render (where workspace is read-only)
    try:
        import shutil
        from pathlib import Path
        src_metadata = Path("/opt/render/project/src/metadata")
        dest_metadata = Path(settings.metadata_path).resolve()
        if src_metadata.exists() and dest_metadata != src_metadata:
            log.info("Copying pre-packaged metadata to writable directory | src={src} | dest={dest}", src=src_metadata, dest=dest_metadata)
            dest_metadata.mkdir(parents=True, exist_ok=True)
            for item in src_metadata.iterdir():
                dest_item = dest_metadata / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest_item)
            log.info("Pre-packaged metadata copy completed successfully.")
    except Exception as exc:
        log.error("Failed to copy pre-packaged metadata | error={error}", error=str(exc))

    # 1. Pre-load BGE embedding model
    try:
        from app.embeddings.embedder import BGEEmbedder
        log.info("Pre-loading BGE embedding model '{model}'...", model=settings.embedding_model_name)
        app.state.embedder = BGEEmbedder(
            model_name=settings.embedding_model_name,
            cache_dir=settings.embedding_cache_dir,
        )
    except Exception as exc:
        log.error("Failed to pre-load embedding model | error={error}", error=str(exc))

    # 2. Initialize Qdrant client and create collection
    try:
        from app.vectorstore import get_qdrant_client, CollectionManager
        log.info("Initializing Qdrant client connection (mode={mode})...", mode=settings.qdrant_mode)
        app.state.qdrant_client = get_qdrant_client(settings)

        # Automatically create collection if it doesn't exist
        CollectionManager.create_collection_if_not_exists(
            client=app.state.qdrant_client,
            collection_name=settings.qdrant_collection_name,
            dimension=384,
        )
    except Exception as exc:
        log.error("Failed to initialize Qdrant vector store | error={error}", error=str(exc))

    # 3. Initialize Elasticsearch client and create index
    try:
        from app.elasticsearch import get_elasticsearch_client, ElasticsearchRepository
        log.info("Initializing Elasticsearch client connection...")
        app.state.elasticsearch_client = get_elasticsearch_client(settings)
        
        # Create index if it does not exist
        es_repo = ElasticsearchRepository(client=app.state.elasticsearch_client, settings=settings)
        es_repo.create_index_if_not_exists()
    except Exception as exc:
        log.error("Failed to initialize Elasticsearch keyword store | error={error}", error=str(exc))

    # 4. Auto-scan dataset if AUTO_SCAN_ON_STARTUP=true
    if settings.auto_scan_on_startup:
        try:
            from app.dataset.dataset_repository import FileSystemDatasetRepository
            from app.dataset.dataset_service import DatasetService
            from pathlib import Path
            repo = FileSystemDatasetRepository(settings)
            dataset_root = Path(settings.dataset_path).resolve()
            metadata_dir = Path(settings.metadata_path).resolve()
            dataset_service = DatasetService(repository=repo, dataset_root=dataset_root, metadata_dir=metadata_dir)
            log.info("AUTO_SCAN_ON_STARTUP is enabled. Running dataset scan...")
            dataset_service.scan_dataset()
        except Exception as exc:
            log.error("Failed auto-scan on startup | error={error}", error=str(exc))

    # 5. Auto-ingest message (requires API trigger for parsing/chunking pipeline)
    if settings.auto_ingest_on_startup:
        log.warning("AUTO_INGEST_ON_STARTUP is true, but bulk ingestion requires pipeline routing triggers.")

    log.info("{name} startup complete. API available at http://{host}:{port}", name=settings.app_name, host=settings.app_host, port=settings.app_port)

    yield  # Application runs here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    log.info("Shutting down {name}...", name=settings.app_name)

    # Close Qdrant client connection
    if hasattr(app.state, "qdrant_client"):
        try:
            log.info("Closing Qdrant client connection...")
            app.state.qdrant_client.close()
        except Exception as exc:
            log.error("Failed to close Qdrant client | error={error}", error=str(exc))

    # Close Elasticsearch client
    if hasattr(app.state, "elasticsearch_client"):
        try:
            log.info("Closing Elasticsearch client connection...")
            app.state.elasticsearch_client.close()
        except Exception as exc:
            log.error("Failed to close Elasticsearch client | error={error}", error=str(exc))

    log.info("Shutdown complete.")



# =============================================================================
# APPLICATION FACTORY
# =============================================================================

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    Returns:
        FastAPI: Fully configured application instance.
    """
    # ── Configure logging first ────────────────────────────────────────────────
    configure_logging(
        log_level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
    )

    # ── Create FastAPI instance ────────────────────────────────────────────────
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Enterprise AI Legal Assistant using Hybrid RAG (Qdrant + Elasticsearch) "
            "for US Tax & Legal document question answering with Google Gemini."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Register CORS middleware ───────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Register custom middlewares ───────────────────────────────────────────
    from app.api.middlewares import (
        RequestResponseLoggingMiddleware,
        ExceptionTranslationMiddleware,
        RateLimitMiddleware,
    )
    application.add_middleware(RequestResponseLoggingMiddleware)
    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(ExceptionTranslationMiddleware)


    # ── Register exception handlers ───────────────────────────────────────────
    _register_exception_handlers(application)

    # ── Register API routers ───────────────────────────────────────────────────
    _register_routers(application)

    return application


def _register_routers(app: FastAPI) -> None:
    """
    Register all API routers under the /api/v1 prefix.

    Args:
        app: The FastAPI application instance.
    """
    from app.api.v1.router import api_router
    app.include_router(api_router, prefix=API_V1_PREFIX)


def _register_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers that translate domain exceptions
    to structured HTTP JSON responses.

    Args:
        app: The FastAPI application instance.
    """
    @app.exception_handler(LegalAssistantError)
    async def domain_exception_handler(request: Request, exc: LegalAssistantError) -> JSONResponse:
        """Handle all custom domain exceptions."""
        log.error(
            "Domain error: {error} | {message}",
            error=type(exc).__name__,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler for unexpected exceptions."""
        log.exception("Unhandled exception: {exc}", exc=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred. Please try again.",
                "detail": {},
            },
        )


# =============================================================================
# APPLICATION INSTANCE (module-level — used by Uvicorn)
# =============================================================================
app: FastAPI = create_app()


# =============================================================================
# HEALTH ENDPOINT (registered directly — not behind /api/v1 prefix)
# =============================================================================
@app.get("/health", tags=["Health"], summary="System health check")
async def health_check() -> dict:
    """
    Returns system health status including dependent service statuses.

    Returns:
        dict: Health status of the application and all services.
    """
    qdrant_status = "uninitialized"
    if hasattr(app.state, "qdrant_client"):
        try:
            # Quick check if connection is active
            app.state.qdrant_client.get_collections()
            qdrant_status = "healthy"
        except Exception:
            qdrant_status = "unhealthy"

    es_status = "uninitialized"
    if hasattr(app.state, "elasticsearch_client"):
        try:
            # Quick check if Elasticsearch is pingable
            if app.state.elasticsearch_client.ping():
                es_status = "healthy"
            else:
                es_status = "unhealthy"
        except Exception:
            es_status = "unhealthy"

    model_status = "uninitialized"
    if hasattr(app.state, "embedder") and app.state.embedder._initialized:
        model_status = "healthy"

    is_healthy = qdrant_status == "healthy" and es_status == "healthy" and model_status == "healthy"

    return {
        "status": "healthy" if is_healthy else "degraded",
        "version": settings.app_version,
        "environment": settings.app_env,
        "services": {
            "qdrant": qdrant_status,
            "elasticsearch": es_status,
            "embedding_model": model_status,
            "llm_provider": settings.llm_provider,
        },
    }


# =============================================================================
# ENTRYPOINT (for direct execution: python main.py)
# =============================================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )
