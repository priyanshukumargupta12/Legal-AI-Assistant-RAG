"""
app/llm/llm_controller.py
==========================
FastAPI controller (router) for the LLM Module.

DEPRECATION WARNING:
    This controller is legacy dead code.
    Active API routes for the LLM Assistant are aggregated in:
        app/api/routes/llm.py
    Refer to that module for production endpoints.
"""


from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.exceptions import LLMError
from app.llm.base_provider import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.conversation_memory import ConversationHistoryMemory
from app.llm.llm_repository import ConversationHistoryRepository
from app.llm.llm_schemas import LLMQueryRequest, LLMQueryResponse, CitationSchema
from app.llm.llm_service import LLMService

router = APIRouter(prefix="/llm", tags=["LLM Assistant"])


# ── Dependency Singletons (LRU Cached) ─────────────────────────────────────────


@lru_cache(maxsize=1)
def get_conversation_repository(settings: Settings) -> ConversationHistoryRepository:
    """Singleton repository for conversation file persistence."""
    return ConversationHistoryRepository(settings)


@lru_cache(maxsize=1)
def get_conversation_memory() -> ConversationHistoryMemory:
    """Singleton sliding-window chat history memory."""
    # Keeps a default window of 10 conversations
    return ConversationHistoryMemory(max_history=10)


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Factory to construct the configured LLM provider."""
    provider_name = settings.llm_provider.lower()
    if provider_name == "gemini":
        return GeminiProvider(settings)
    elif provider_name == "openai":
        return OpenAIProvider(settings)
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def get_llm_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMService:
    """Dependency: constructs a fully hydrated LLMService."""
    provider = get_llm_provider(settings)
    repo = get_conversation_repository(settings)
    memory = get_conversation_memory()
    return LLMService(
        provider=provider,
        repository=repo,
        memory=memory,
        settings=settings,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.delete(
    "/memory/clear",
    summary="Clear Conversation History",
    description="Resets the active sliding-window chat history and wipes the local storage file.",
)
def clear_memory(
    service: Annotated[LLMService, Depends(get_llm_service)],
) -> Dict[str, str]:
    """Clears conversation history states."""
    service.clear_memory()
    return {"status": "success", "message": "Conversation history memory has been cleared."}


@router.get(
    "/health",
    summary="LLM Provider Connectivity Check",
    description="Tests connection and credential health for the configured LLM provider.",
)
async def provider_health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Dict[str, Any]:
    """Checks the health of the active LLM provider API."""
    try:
        provider = get_llm_provider(settings)
        healthy = await provider.health_check()
        if not healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM Provider API '{settings.llm_provider}' is unreachable.",
            )
        return {
            "status": "healthy",
            "provider": settings.llm_provider,
            "model": settings.gemini_model if settings.llm_provider == "gemini" else settings.openai_model,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
