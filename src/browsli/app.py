from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, Markdown, Static

from .config import load_config
from .fetch import BrowserRenderer, StaticFetcher
from .models import BrowserDocument
from .session import BrowserSession
from .transformer import Transformer


class DocumentView(Markdown):
    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("open_links", False)
        super().__init__(*args, **kwargs)
        self.renderable: object = ""

    def update(self, renderable: object = "") -> None:
        self.renderable = renderable
        return super().update(str(renderable))


class LinkListItem(ListItem):
    def __init__(self, link_id: int, label: Static) -> None:
        super().__init__(label)
        self.link_id = link_id


class BrowsliApp(App):
    CSS = """
    #address { dock: top; }
    #document { width: 2fr; padding: 1; }
    #links { width: 1fr; border-left: solid $accent; }
    """
    BINDINGS = [
        ("ctrl+p", "focus_address", "Command"),
        Binding("alt+left", "back", "Back", priority=True),
        Binding("alt+right", "forward", "Forward", priority=True),
        Binding("alt-left", "back", "Back", priority=True),
        Binding("alt-right", "forward", "Forward", priority=True),
        Binding("ctrl+left", "back", "Back", priority=True),
        Binding("ctrl+right", "forward", "Forward", priority=True),
    ]

    def __init__(self, session: BrowserSession | None = None) -> None:
        super().__init__()
        self._session = session or build_session()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(id="address")
        with Horizontal():
            yield DocumentView(id="document")
            with Vertical(id="links"):
                yield Static("Links")
                yield ListView(id="link-list")
        yield Footer()

    async def on_mount(self) -> None:
        if self._session.current is not None:
            await self._render_document(self._session.current)
        else:
            await self.query_one("#document", DocumentView).update("Enter a search query or URL.")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        if value.startswith(("http://", "https://")):
            doc = await self._session.open_url(value)
        else:
            doc = await self._session.search(value)
        await self._render_document(doc)

    async def action_back(self) -> None:
        await self._render_document(await self._session.back())

    async def action_forward(self) -> None:
        await self._render_document(await self._session.forward())

    def action_focus_address(self) -> None:
        self.query_one("#address", Input).focus()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        link_id = event.item.link_id
        await self._render_document(await self._session.open_link(link_id))

    async def _render_document(self, document: BrowserDocument) -> None:
        status = f"\n\nStatus: {document.status}" if document.status else ""
        await self.query_one("#document", DocumentView).update(f"{document.content}{status}")
        link_list = self.query_one("#link-list", ListView)
        link_list.clear()
        for link in document.links:
            link_list.append(LinkListItem(link.id, Static(f"[{link.id}] {link.text}\n{link.url}")))


def build_session() -> BrowserSession:
    from .config import ProviderConfig
    from .models import SearchResult
    from .providers import LLMProvider, SearchProvider

    class LazyLLMProvider:
        def __init__(self, config: ProviderConfig) -> None:
            self._config = config
            self._provider: LLMProvider | None = None

        async def complete(self, prompt: str) -> str:
            if self._provider is None:
                from .providers import build_llm_provider

                self._provider = build_llm_provider(self._config)
            return await self._provider.complete(prompt)

    class LazySearchProvider:
        def __init__(self, config: ProviderConfig) -> None:
            self._config = config
            self._provider: SearchProvider | None = None

        async def search(self, query: str) -> tuple[SearchResult, ...]:
            if self._provider is None:
                from .providers import TavilySearchProvider

                self._provider = TavilySearchProvider(self._config)
            return await self._provider.search(query)

    config = load_config()
    llm = LazyLLMProvider(config.llm)
    search = LazySearchProvider(config.search)
    transformer = Transformer(llm)
    static_fetcher = StaticFetcher(config.static_fetch_timeout_seconds)
    browser_fetcher = (
        BrowserRenderer(config.static_fetch_timeout_seconds)
        if config.browser_fallback_enabled
        else None
    )
    return BrowserSession(
        search,
        static_fetcher,
        browser_fetcher,
        transformer,
        browser_fallback_enabled=config.browser_fallback_enabled,
    )
