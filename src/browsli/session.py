from __future__ import annotations

from .extractor import HtmlExtractor
from .links import LinkRegistry
from .models import BrowserDocument, DocumentKind, ExtractedDocument, ProviderError, SearchResult
from .providers.base import SearchProvider
from .transformer import Transformer


class BrowserSession:
    def __init__(
        self,
        search_provider: SearchProvider,
        static_fetcher,
        browser_fetcher,
        transformer: Transformer,
        *,
        browser_fallback_enabled: bool,
    ) -> None:
        self._search_provider = search_provider
        self._static_fetcher = static_fetcher
        self._browser_fetcher = browser_fetcher
        self._transformer = transformer
        self._browser_fallback_enabled = browser_fallback_enabled
        self._extractor = HtmlExtractor()
        self._current: BrowserDocument | None = None
        self._back: list[BrowserDocument] = []
        self._forward: list[BrowserDocument] = []
        self._cache: dict[str, BrowserDocument] = {}

    @property
    def current(self) -> BrowserDocument | None:
        return self._current

    async def search(self, query: str) -> BrowserDocument:
        try:
            results = await self._search_provider.search(query)
            doc = await self._search_document(query, results)
        except ProviderError as error:
            doc = self._error_document(f"Search failed: {query}", query, str(error))
        self._navigate(doc)
        return doc

    async def open_url(self, url: str) -> BrowserDocument:
        if url in self._cache:
            doc = self._cache[url]
            self._navigate(doc)
            return doc

        try:
            html = await self._static_fetcher.fetch(url)
            extracted = self._extractor.extract(url, html)
            if (
                extracted.js_dependent
                and self._browser_fallback_enabled
                and self._browser_fetcher is not None
            ):
                html = await self._browser_fetcher.fetch(url)
                extracted = self._extractor.extract(url, html)
            elif extracted.js_dependent:
                doc = self._error_document(
                    "Unsupported JavaScript page", url, "browser fallback is disabled"
                )
                self._navigate(doc)
                return doc

            transformed = await self._transformer.transform(extracted)
            doc = BrowserDocument(
                kind=DocumentKind.PAGE,
                title=extracted.title,
                source=url,
                content=transformed.content,
                links=extracted.links,
                transformed=transformed.transformed,
                status=transformed.status,
            )
            self._cache[url] = doc
        except ProviderError as error:
            doc = self._error_document(f"Open failed: {url}", url, str(error))
        self._navigate(doc)
        return doc

    async def open_link(self, link_id: int) -> BrowserDocument:
        if self._current is None:
            return self._error_document("No document", "", "no current document")
        link = next((link for link in self._current.links if link.id == link_id), None)
        if link is None:
            return self._error_document(
                f"Unknown link: {link_id}", self._current.source, f"unknown link {link_id}"
            )
        return await self.open_url(link.url)

    async def back(self) -> BrowserDocument:
        if self._current is not None and self._back:
            self._forward.append(self._current)
            self._current = self._back.pop()
        return self._current or self._error_document("No document", "", "back stack is empty")

    async def forward(self) -> BrowserDocument:
        if self._current is not None and self._forward:
            self._back.append(self._current)
            self._current = self._forward.pop()
        return self._current or self._error_document("No document", "", "forward stack is empty")

    async def _search_document(
        self, query: str, results: tuple[SearchResult, ...]
    ) -> BrowserDocument:
        raw_links = [(result.title, result.url) for result in results]
        links = LinkRegistry.from_raw_links(raw_links).links
        lines = [f"Search results for {query}"]
        for index, result in enumerate(results, start=1):
            lines.append(f"[{index}] {result.title}\n{result.snippet}\n{result.url}")
        extracted = ExtractedDocument(
            source_url=f"search:{query}",
            title=f"Search: {query}",
            text="\n\n".join(lines),
            links=links,
        )
        transformed = await self._transformer.transform(extracted)
        return BrowserDocument(
            kind=DocumentKind.SEARCH,
            title=f"Search: {query}",
            source=query,
            content=transformed.content,
            links=links,
            transformed=transformed.transformed,
            status=transformed.status,
        )

    def _navigate(self, doc: BrowserDocument) -> None:
        if self._current is not None:
            self._back.append(self._current)
        self._current = doc
        self._forward.clear()

    def _error_document(self, title: str, source: str, status: str) -> BrowserDocument:
        return BrowserDocument(
            kind=DocumentKind.ERROR, title=title, source=source, content=status, status=status
        )

