import pytest

from browsli.app import BrowsliApp
from browsli.models import BrowserDocument, DocumentKind


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


@pytest.mark.asyncio
async def test_app_launches_and_renders_initial_document() -> None:
    app = BrowsliApp(session=FakeSession())

    async with app.run_test() as pilot:
        assert app.query_one("#document").renderable == "Welcome"
        await pilot.press("ctrl+p")

