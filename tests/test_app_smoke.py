import pytest

from browsli.app import BrowsliApp, build_session
from browsli.models import BrowserDocument, DocumentKind, Link


class FakeSession:
    current = BrowserDocument(DocumentKind.PAGE, "Home", "local", "Welcome", ())

    async def search(self, query: str):
        self.current = BrowserDocument(DocumentKind.SEARCH, f"Search: {query}", query, "Results", ())
        return self.current

    async def open_url(self, url: str):
        self.current = BrowserDocument(DocumentKind.PAGE, url, url, "Page", ())
        return self.current

    async def open_link(self, link_id: int):
        self.current = BrowserDocument(DocumentKind.PAGE, "Link", str(link_id), "Linked", ())
        return self.current

    async def back(self):
        return self.current

    async def forward(self):
        return self.current


class LinkedFakeSession:
    current = BrowserDocument(
        DocumentKind.PAGE,
        "First",
        "local",
        "First page",
        (Link(1, "Next", "https://example.com/next"),),
    )

    async def search(self, query: str):
        return self.current

    async def open_url(self, url: str):
        return self.current

    async def open_link(self, link_id: int):
        self.current = BrowserDocument(
            DocumentKind.PAGE,
            "Second",
            str(link_id),
            "Second page",
            (Link(1, "Again", "https://example.com/again"),),
        )
        return self.current

    async def back(self):
        return self.current

    async def forward(self):
        return self.current


@pytest.mark.asyncio
async def test_app_launches_and_renders_initial_document() -> None:
    app = BrowsliApp(session=FakeSession())

    async with app.run_test() as pilot:
        assert app.query_one("#document").renderable == "Welcome"
        await pilot.press("ctrl+p")


@pytest.mark.asyncio
async def test_build_session_defers_missing_search_api_key_until_first_use(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    session = build_session()
    doc = await session.search("python")

    assert doc.kind == DocumentKind.ERROR
    assert "TAVILY_API_KEY" in doc.status


@pytest.mark.asyncio
async def test_app_can_render_reused_link_ids_after_opening_link() -> None:
    app = BrowsliApp(session=LinkedFakeSession())

    async with app.run_test():
        app._render_document(
            BrowserDocument(
                DocumentKind.PAGE,
                "Second",
                "local",
                "Second page",
                (Link(1, "Again", "https://example.com/again"),),
            )
        )

        assert app.query_one("#document").renderable == "Second page"
