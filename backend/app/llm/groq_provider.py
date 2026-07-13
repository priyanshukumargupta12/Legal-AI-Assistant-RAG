"""
app/llm/groq_provider.py
========================
Groq LLM provider implementation.

PURPOSE:
    Implements LLMProvider using langchain-openai pointing to the Groq endpoint.
    Active when llm_provider=groq in settings.

MODEL: llama-3.3-70b-versatile (configurable via Settings)
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from app.core.config import Settings
from app.core.exceptions import LLMError
from app.llm.base_provider import LLMProvider
from app.llm.llm_logger import llm_log


class GroqProvider(LLMProvider):
    """
    Groq implementation of LLMProvider.

    Wired using ChatOpenAI pointing to Groq's OpenAI-compatible API base URL.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.groq_model
        self.api_key = settings.groq_api_key

        if not self.api_key or self.api_key.startswith("<YOUR_"):
            llm_log.warning("GROQ_API_KEY is not configured in settings.")

        self._model = self._build_chat_model()

    def _build_chat_model(self) -> ChatOpenAI:
        """Constructs and returns the ChatOpenAI instance for Groq."""
        api_key = "DUMMY_KEY" if (not self.api_key or self.api_key.startswith("<YOUR_")) else self.api_key
        return ChatOpenAI(
            model=self.model_name,
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.0,  # Enforce determinism
            max_tokens=2048,
        )

    async def generate(self, prompt: str) -> str:
        """
        Generate response content using Groq API.

        Raises:
            LLMError: If Groq invocation fails.
        """
        if not self.api_key or self.api_key.startswith("<YOUR_"):
            raise LLMError("Groq API Key is missing. Check configuration.", provider="groq")

        llm_log.info(
            "Generating LLM response | provider=groq | model={model} | prompt_len={plen}",
            model=self.model_name,
            plen=len(prompt),
        )

        try:
            response = await self._model.ainvoke(prompt)
            raw_text = str(response.content).strip()

            llm_log.info(
                "Groq response generated successfully | response_len={rlen}",
                rlen=len(raw_text),
            )
            return raw_text

        except Exception as exc:
            llm_log.error("Groq invocation failed | error={err}", err=str(exc))
            raise LLMError(
                message=f"Groq API invocation failed: {exc}",
                provider="groq",
            ) from exc

    async def health_check(self) -> bool:
        """Check if the Groq API is reachable by running a simple test invoke."""
        if not self.api_key or self.api_key.startswith("<YOUR_"):
            return False

        try:
            test_model = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1",
                max_tokens=10,
            )
            await test_model.ainvoke("ping")
            return True
        except Exception as exc:
            llm_log.warning("Groq health check failed | error={err}", err=str(exc))
            return False
