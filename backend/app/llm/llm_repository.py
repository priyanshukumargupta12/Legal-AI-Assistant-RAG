"""
app/llm/llm_repository.py
=========================
Repository for persisting and managing conversation history.

PURPOSE:
    Provides methods to save, load, and clear conversation history records
    to a persistent JSON file or in-memory cache, satisfying Clean Architecture.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.config import Settings
from app.llm.llm_logger import llm_log
from app.llm.llm_models import ChatMessage


class ConversationHistoryRepository:
    """
    Handles persistence of conversation messages.

    Saves chat messages to a local JSON file for persistence across restarts.

    Args:
        settings: Application Settings containing paths.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Persist conversation history to app logs directory
        log_dir = Path(settings.log_dir)
        self.history_path = log_dir / "conversation_history.json"
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create the history file and parent directories if missing."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.history_path.exists():
                with open(self.history_path, "w", encoding="utf-8") as fh:
                    json.dump([], fh)
        except Exception as exc:
            llm_log.error("Failed to initialize conversation history file | error={err}", err=str(exc))

    def save_messages(self, messages: List[ChatMessage]) -> None:
        """
        Overwrites the history file with the provided active messages.
        """
        try:
            payload = []
            for msg in messages:
                payload.append(
                    {
                        "question": msg.question,
                        "answer": msg.answer,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                )
            with open(self.history_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            llm_log.info("Saved conversation history | count={count}", count=len(messages))
        except Exception as exc:
            llm_log.error("Failed to save conversation history | error={err}", err=str(exc))

    def load_messages(self) -> List[ChatMessage]:
        """
        Loads and returns persisted conversation history messages.
        """
        if not self.history_path.exists():
            return []

        try:
            with open(self.history_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            messages: List[ChatMessage] = []
            if isinstance(data, list):
                for item in data:
                    timestamp_str = item.get("timestamp")
                    try:
                        ts = datetime.fromisoformat(timestamp_str)
                    except (ValueError, TypeError):
                        ts = datetime.now(timezone.utc)

                    messages.append(
                        ChatMessage(
                            question=item.get("question", ""),
                            answer=item.get("answer", ""),
                            timestamp=ts,
                        )
                    )
            return messages
        except Exception as exc:
            llm_log.error("Failed to load conversation history | error={err}", err=str(exc))
            return []

    def clear(self) -> None:
        """Clears the persistent history storage."""
        try:
            with open(self.history_path, "w", encoding="utf-8") as fh:
                json.dump([], fh)
            llm_log.info("Cleared conversation history file")
        except Exception as exc:
            llm_log.error("Failed to clear conversation history file | error={err}", err=str(exc))
