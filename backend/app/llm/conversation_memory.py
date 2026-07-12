"""
app/llm/conversation_memory.py
================================
Manages context and conversation history across turns.

PURPOSE:
    Uses LangChain Core's InMemoryChatMessageHistory to persist QA exchanges,
    allowing coherent follow-up question processing using modern, stable patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage
from app.llm.llm_models import ChatMessage


class ConversationHistoryMemory:
    """
    Manages chat history window utilizing LangChain Core's message history.

    Args:
        max_history: Max conversation turns to retain (default: 10).
    """

    def __init__(self, max_history: int = 10) -> None:
        self.max_history = max_history
        self._history = InMemoryChatMessageHistory()
        self._history_records: List[ChatMessage] = []

    def add_exchange(self, question: str, answer: str) -> None:
        """Saves a single question/answer exchange to memory."""
        # 1. Add to LangChain memory history
        self._history.add_message(HumanMessage(content=question))
        self._history.add_message(AIMessage(content=answer))

        # 2. Store domain entity locally
        self._history_records.append(
            ChatMessage(
                question=question,
                answer=answer,
                timestamp=datetime.now(timezone.utc),
            )
        )

        # 3. Prune both to match sliding window size (2 messages per exchange)
        max_messages = self.max_history * 2
        messages = self._history.messages
        if len(messages) > max_messages:
            # Recreate with sliced list of messages
            trimmed_messages = messages[-max_messages:]
            self._history.clear()
            for msg in trimmed_messages:
                self._history.add_message(msg)

        if len(self._history_records) > self.max_history:
            self._history_records.pop(0)

    def get_history_string(self) -> str:
        """Returns the history formatted as a single string for prompt inclusion."""
        messages = self._history.messages
        if not messages:
            return "No prior exchanges."

        formatted_lines = []
        # Group human/AI messages by turn
        for i in range(0, len(messages), 2):
            if i + 1 < len(messages):
                h_msg = messages[i].content
                ai_msg = messages[i+1].content
                formatted_lines.append(f"Human: {h_msg}\nAssistant: {ai_msg}")
        return "\n\n".join(formatted_lines)

    def get_messages(self) -> List[ChatMessage]:
        """Returns the list of ChatMessage domain objects."""
        return self._history_records

    def clear(self) -> None:
        """Clears all conversation memory."""
        self._history.clear()
        self._history_records.clear()
