"""
llm/base_provider.py
=====================
Abstract LLM provider interface.

PURPOSE:
    Defines the contract that all LLM providers (Gemini, OpenAI) must implement.
    Services depend on this abstraction; concrete providers implement it.

SOLID: Dependency Inversion — application layer depends on this interface.
       Open/Closed — new LLM providers added without touching existing code.
       Liskov Substitution — any LLMProvider can replace another.
"""

from __future__ import annotations
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for LLM generation providers."""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM given a fully assembled prompt.

        Args:
            prompt: Complete prompt string (system + context + question).

        Returns:
            Raw LLM response string (expected to be JSON-structured).

        Raises:
            LLMError: If the API call fails after all retries.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the LLM provider API is reachable."""
        ...
