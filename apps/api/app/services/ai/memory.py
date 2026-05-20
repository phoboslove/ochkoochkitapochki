"""Conversation memory layer.

In-memory implementation for the scaffold. Production replaces this with a
DB-backed repository over the `Message` / `Conversation` tables, plus optional
vector recall over company documents.
"""
from collections import defaultdict
from typing import Any


class ConversationMemory:
    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def append(self, conversation_id: str, *, role: str, content: str) -> None:
        self._store[conversation_id].append({"role": role, "content": content})

    def history(self, conversation_id: str) -> list[dict[str, Any]]:
        return list(self._store[conversation_id])
