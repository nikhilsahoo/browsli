import pytest
from textual.widgets import Markdown

from browsli.app import BrowsliApp, build_session
from browsli.models import BrowserDocument, DocumentKind, Link


class FakeSession:
    current = BrowserDocument(DocumentKind.PAGE, "Home", "local", "Welcome", ())

    async def search(self, query: str, *, on_update=None):
        self.current = BrowserDocument(DocumentKind.SEARCH, f"Search: {query}", query, "Results", ())
        if on_update is not None:
            await on_update(self.current)
        return self.current

    async def open_url(self, url: str, *, on_update=None):
        self.current = BrowserDocument(DocumentKind.PAGE, url, url, "Page", ())
        if on_update is not None:
            await on_update(self.current)
        return self.current

    async def open_link(self, link_id: int, *, on_update=None):
        self.current = BrowserDocument(DocumentKind.PAGE, "Link", str(link_id), "Linked", ())
        if on_update is not None:
            await on_update(self.current)
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

    async def search(self, query: str, *, on_update=None):
        return self.current

    async def open_url(self, url: str, *, on_update=None):
        return self.current

    async def open_link(self, link_id: int, *, on_update=None):
        self.current = BrowserDocument(
            DocumentKind.PAGE,
            "Second",
            str(link_id),
            "Second page",
            (Link(1, "Again", "https://example.com/again"),),
        )
        if on_update is not None:
            await on_update(self.current)
        return self.current

    async def back(self):
        return self.current

    async def forward(self):
        return self.current


class NavigationFakeSession:
    current = BrowserDocument(DocumentKind.PAGE, "Current", "local", "Current page", ())

    async def search(self, query: str, *, on_update=None):
        return self.current

    async def open_url(self, url: str, *, on_update=None):
        return self.current

    async def open_link(self, link_id: int, *, on_update=None):
        return self.current

    async def back(self):
        self.current = BrowserDocument(DocumentKind.PAGE, "Back", "local", "Back page", ())
        return self.current

    async def forward(self):
        self.current = BrowserDocument(DocumentKind.PAGE, "Forward", "local", "Forward page", ())
        return self.current


class LongDocumentFakeSession:
    current = BrowserDocument(
        DocumentKind.PAGE,
        "Long",
        "local",
        "\n\n".join(f"Line {index}" for index in range(200)),
        (),
    )

    async def search(self, query: str, *, on_update=None):
        return self.current

    async def open_url(self, url: str, *, on_update=None):
        return self.current

    async def open_link(self, link_id: int, *, on_update=None):
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
        await app._render_document(
            BrowserDocument(
                DocumentKind.PAGE,
                "Second",
                "local",
                "Second page",
                (Link(1, "Again", "https://example.com/again"),),
            )
        )

        assert app.query_one("#document").renderable == "Second page"


@pytest.mark.asyncio
async def test_app_uses_markdown_document_pane() -> None:
    app = BrowsliApp(session=FakeSession())

    async with app.run_test():
        assert app.query_one("#document", Markdown).renderable == "Welcome"


def test_app_document_pane_is_scrollable() -> None:
    assert "overflow-y: scroll" in BrowsliApp.CSS


def test_app_exposes_quit_key_binding() -> None:
    assert any(binding.key == "ctrl+q" and binding.description == "Quit" for binding in BrowsliApp.BINDINGS)


@pytest.mark.asyncio
async def test_app_document_pane_height_is_bounded_for_long_content() -> None:
    app = BrowsliApp(session=LongDocumentFakeSession())

    async with app.run_test(size=(100, 30)):
        document = app.query_one("#document", Markdown)

        assert document.size.height < 30
        assert document.max_scroll_y > 0


@pytest.mark.asyncio
async def test_alt_and_ctrl_arrow_keys_navigate_back_and_forward() -> None:
    app = BrowsliApp(session=NavigationFakeSession())

    async with app.run_test() as pilot:
        await pilot.press("alt+left")
        assert app.query_one("#document").renderable == "Back page"

        await pilot.press("alt+right")
        assert app.query_one("#document").renderable == "Forward page"

        await pilot.press("ctrl+left")
        assert app.query_one("#document").renderable == "Back page"

        await pilot.press("ctrl+right")
        assert app.query_one("#document").renderable == "Forward page"
