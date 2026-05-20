"""Common interface every integration adapter implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IntegrationAdapter(ABC):
    provider: str

    @abstractmethod
    async def connect(self, config: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def test(self) -> dict[str, Any]: ...

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
