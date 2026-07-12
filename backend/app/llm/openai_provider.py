"""
app/llm/openai_provider.py
===========================
OpenAI LLM provider implementation (optional fallback).

PURPOSE:
    Implements LLMProvider using langchain-openai.
    Active when llm_provider=openai in settings.

MODEL: gpt-4o-mini (configurable via Settings)
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from app.core.config import Settings
from app.core.exceptions import LLMError
from app.llm.base_provider import LLMProvider
from app.llm.llm_logger import llm_log


class OpenAIProvider(LLMProvider):
    """
    OpenAI implementation of LLMProvider.

    Wired using ChatOpenAI from langchain_openai.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.openai_model
        self.api_key = settings.openai_api_key

        if not self.api_key:
            llm_log.warning("OPENAI_API_KEY is not configured in settings.")

        self._model = self._build_chat_model()

    def _build_chat_model(self) -> ChatOpenAI:
        """Constructs and returns the ChatOpenAI instance."""
        return ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            temperature=0.0,  # Enforce determinism
            max_tokens=2048,
        )

    async def generate(self, prompt: str) -> str:
        """
        Generate response content using OpenAI API.

        Raises:
            LLMError: If OpenAI invocation fails.
        """
        if not self.api_key:
            raise LLMError("OpenAI API Key is missing. Check configuration.", provider="openai")

        llm_log.info(
            "Generating LLM response | provider=openai | model={model} | prompt_len={plen}",
            model=self.model_name,
            plen=len(prompt),
        )

        try:
            response = await self._model.ainvoke(prompt)
            raw_text = str(response.content).strip()

            llm_log.info(
                "OpenAI response generated successfully | response_len={rlen}",
                rlen=len(raw_text),
            )
            return raw_text

        except Exception as exc:
            llm_log.error("OpenAI invocation failed | error={err}", err=str(exc))
            raise LLMError(
                message=f"OpenAI API invocation failed: {exc}",
                provider="openai",
            ) from exc

    async def health_check(self) -> bool:
        """Check if the OpenAI API is reachable by running a simple test invoke."""
        if not self.api_key:
            return False

        try:
            test_model = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                max_tokens=10,
            )
            await test_model.ainvoke("ping")
            return True
        except Exception as exc:
            llm_log.warning("OpenAI health check failed | error={err}", err=str(exc))
            return False
