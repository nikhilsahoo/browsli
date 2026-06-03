from __future__ import annotations

from typing import Protocol

from browsli.models import SearchResult


class LLMProvider(Protocol):
    async def complete(self, prompt: str) -> str: ...


class SearchProvider(Protocol):
    async def search(self, query: str) -> tuple[SearchResult, ...]: ...

