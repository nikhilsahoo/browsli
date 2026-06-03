import pytest

from browsli.models import DocumentKind, ExtractedDocument, ProviderError, SearchResult
from browsli.session import BrowserSession


class FakeSearch:
    async def search(self, query: str) -> tuple[SearchResult, ...]:
        return (SearchResult("Result", "https://example.com/page", "Snippet"),)


class FailingSearch:
    async def search(self, query: str) -> tuple[SearchResult, ...]:
        raise ProviderError("tavily", "api", "down")


class FakeFetcher:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, url: str) -> str:
        self.calls += 1
        return '<html><head><title>Page</title></head><body><a href="/next">Next</a><p>Body</p></body></html>'


class FakeTransformer:
    async def transform(self, document: ExtractedDocument):
        from browsli.transformer import TransformResult

        return TransformResult(f"Condensed {document.title} [1]", True)


@pytest.mark.asyncio
async def test_session_search_open_link_and_back_forward() -> None:
    fetcher = FakeFetcher()
    session = BrowserSession(
        FakeSearch(), fetcher, None, FakeTransformer(), browser_fallback_enabled=False
    )

    search_doc = await session.search("python")
    assert search_doc.kind == DocumentKind.SEARCH
    assert search_doc.links[0].url == "https://example.com/page"

    page_doc = await session.open_link(1)
    assert page_doc.kind == DocumentKind.PAGE
    assert page_doc.content == "Condensed Page [1]"

    assert (await session.back()).kind == DocumentKind.SEARCH
    assert (await session.forward()).kind == DocumentKind.PAGE


@pytest.mark.asyncio
async def test_session_uses_page_cache() -> None:
    fetcher = FakeFetcher()
    session = BrowserSession(
        FakeSearch(), fetcher, None, FakeTransformer(), browser_fallback_enabled=False
    )

    await session.open_url("https://example.com/page")
    await session.open_url("https://example.com/page")

    assert fetcher.calls == 1


@pytest.mark.asyncio
async def test_search_failure_keeps_error_document_usable() -> None:
    session = BrowserSession(
        FailingSearch(), FakeFetcher(), None, FakeTransformer(), browser_fallback_enabled=False
    )

    doc = await session.search("python")

    assert doc.kind == DocumentKind.ERROR
    assert "tavily api: down" in doc.status

