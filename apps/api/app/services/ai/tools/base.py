"""Tool framework for the AI orchestrator.

Every action the LLM can take is expressed as a `Tool`. Tools declare a JSON
schema (used for OpenAI function calling / Anthropic tool use), validate input
with Pydantic, and execute through a controlled service. Tools that change
state must route through the approval/audit layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class Tool(ABC):
    name: str
    description: str
    input_model: type[BaseModel]
    requires_approval: bool = False

    @abstractmethod
    async def run(self, *, company_id: str, actor_id: str, args: BaseModel) -> dict[str, Any]:
        ...

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }
