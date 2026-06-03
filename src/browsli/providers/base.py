from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from browsli.models import SearchResult


class LLMProvider(Protocol):
    async def complete(self, prompt: str) -> str: ...

    async def stream_complete(self, prompt: str) -> AsyncIterator[str]: ...


class SearchProvider(Protocol):
    async def search(self, query: str) -> tuple[SearchResult, ...]: ...

