from __future__ import annotations

import asyncio
from typing import Any

from tavily import TavilyClient

from browsli.config import ProviderConfig
from browsli.models import ProviderError, SearchResult


class TavilySearchProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self._api_key = config.require_api_key()
        self._timeout = config.timeout_seconds

    async def search(self, query: str) -> tuple[SearchResult, ...]:
        def run_search() -> dict[str, Any]:
            client = TavilyClient(api_key=self._api_key)
            return client.search(query=query, max_results=10)

        try:
            data = await asyncio.wait_for(asyncio.to_thread(run_search), timeout=self._timeout)
        except asyncio.TimeoutError as error:
            raise ProviderError("tavily", "timeout", "search request timed out") from error
        except Exception as error:
            raise ProviderError("tavily", "api", str(error)) from error

        results = data.get("results", [])
        return tuple(
            SearchResult(
                title=str(item.get("title", item.get("url", "Untitled"))),
                url=str(item.get("url", "")),
                snippet=str(item.get("content", "")),
            )
            for item in results
            if item.get("url")
        )

