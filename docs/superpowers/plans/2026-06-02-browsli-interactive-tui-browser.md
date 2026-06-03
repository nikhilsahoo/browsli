# Browsli Interactive TUI Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Browsli as a Textual TUI browser that supports both search and URL browsing, uses LiteLLM and Tavily through adapters, preserves hyperlinks as numbered/selectable anchors, and handles provider failures as UI states.

**Architecture:** Keep a UI-independent browser core with typed document models, link registry, extraction, transformation, providers, fetching, caching, and navigation. Textual owns only rendering and input, calling `BrowserSession` methods for search, open URL, open link, back, and forward.

**Tech Stack:** Python 3.12, Textual, httpx, BeautifulSoup, LiteLLM Python SDK, Tavily Python SDK, pytest, pytest-asyncio, platformdirs, Playwright for config-gated browser fallback.

---

## File Structure

Create or modify these files:

- Modify `pyproject.toml`: add runtime and test dependencies.
- Modify `src/browsli/__init__.py`: console entry point delegates to Textual app.
- Create `src/browsli/models.py`: immutable app-level models and exception types.
- Create `src/browsli/config.py`: TOML/env configuration loader.
- Create `src/browsli/links.py`: link registry and link-token validation.
- Create `src/browsli/extractor.py`: HTML-to-extracted-document conversion and URL resolution.
- Create `src/browsli/providers/__init__.py`: provider exports.
- Create `src/browsli/providers/base.py`: provider protocols.
- Create `src/browsli/providers/litellm_provider.py`: LiteLLM adapter.
- Create `src/browsli/providers/tavily_provider.py`: Tavily adapter.
- Create `src/browsli/fetch.py`: static HTTP fetch and config-gated browser-render fallback.
- Create `src/browsli/transformer.py`: readable condensation and link-token safety.
- Create `src/browsli/session.py`: browser session, navigation stack, synthetic search documents, cache, error documents.
- Create `src/browsli/app.py`: Textual app shell.
- Create `tests/test_config.py`.
- Create `tests/test_links.py`.
- Create `tests/test_extractor.py`.
- Create `tests/test_transformer.py`.
- Create `tests/test_session.py`.
- Create `tests/test_app_smoke.py`.

---

### Task 1: Project Dependencies and Test Harness

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add dependencies**

Run:

```bash
uv add textual httpx beautifulsoup4 litellm tavily-python platformdirs playwright
uv add --dev pytest pytest-asyncio
```

Expected: `pyproject.toml` contains runtime dependencies and dev dependencies.

- [ ] **Step 2: Add pytest configuration**

Modify `pyproject.toml` to include:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Write a first config test**

Create `tests/test_config.py`:

```python
from browsli.config import AppConfig, ProviderConfig


def test_default_config_values() -> None:
    config = AppConfig.default()

    assert config.search.name == "tavily"
    assert config.llm.name == "litellm"
    assert config.cache.mode == "memory"
    assert config.browser_fallback_enabled is False


def test_provider_config_reads_api_key_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "secret")

    provider = ProviderConfig(name="tavily", api_key_env="TAVILY_API_KEY")

    assert provider.require_api_key() == "secret"
```

- [ ] **Step 4: Run test to verify it fails before config exists**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'browsli.config'`.

- [ ] **Step 5: Commit dependency setup and failing test**

Run:

```bash
git add pyproject.toml tests/test_config.py
git commit -m "test: define config defaults"
```

---

### Task 2: Core Models and Configuration

**Files:**
- Create: `src/browsli/models.py`
- Create: `src/browsli/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Implement app models**

Create `src/browsli/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class DocumentKind(str, Enum):
    SEARCH = "search"
    PAGE = "page"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Link:
    id: int
    text: str
    url: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    source_url: str
    title: str
    text: str
    links: tuple[Link, ...]
    js_dependent: bool = False


@dataclass(frozen=True, slots=True)
class BrowserDocument:
    kind: DocumentKind
    title: str
    source: str
    content: str
    links: tuple[Link, ...] = field(default_factory=tuple)
    transformed: bool = True
    status: str = ""


@dataclass(frozen=True, slots=True)
class ProviderError(Exception):
    provider: str
    category: Literal["config", "auth", "timeout", "network", "api", "unsupported"]
    message: str

    def __str__(self) -> str:
        return f"{self.provider} {self.category}: {self.message}"
```

- [ ] **Step 2: Implement config loading**

Create `src/browsli/config.py`:

```python
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from platformdirs import user_config_path

from .models import ProviderError


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: str
    api_key_env: str | None = None
    model: str | None = None
    timeout_seconds: float = 30.0

    def require_api_key(self) -> str:
        if self.api_key_env is None:
            raise ProviderError(self.name, "config", f"{self.name} has no api_key_env configured")
        value = os.getenv(self.api_key_env)
        if not value:
            raise ProviderError(self.name, "config", f"missing environment variable {self.api_key_env}")
        return value


@dataclass(frozen=True, slots=True)
class CacheConfig:
    mode: Literal["memory"] = "memory"


@dataclass(frozen=True, slots=True)
class AppConfig:
    search: ProviderConfig
    llm: ProviderConfig
    cache: CacheConfig
    static_fetch_timeout_seconds: float
    browser_fallback_enabled: bool

    @classmethod
    def default(cls) -> "AppConfig":
        return cls(
            search=ProviderConfig(name="tavily", api_key_env="TAVILY_API_KEY", timeout_seconds=20.0),
            llm=ProviderConfig(name="litellm", model="openai/gpt-4o-mini", timeout_seconds=45.0),
            cache=CacheConfig(),
            static_fetch_timeout_seconds=20.0,
            browser_fallback_enabled=False,
        )


def default_config_path() -> Path:
    return user_config_path("browsli") / "config.toml"


def load_config(path: Path | None = None) -> AppConfig:
    target = path or default_config_path()
    if not target.exists():
        return AppConfig.default()

    data = tomllib.loads(target.read_text(encoding="utf-8"))
    default = AppConfig.default()
    search_data = data.get("search", {})
    llm_data = data.get("llm", {})
    cache_data = data.get("cache", {})
    fetch_data = data.get("fetch", {})

    return AppConfig(
        search=ProviderConfig(
            name=str(search_data.get("name", default.search.name)),
            api_key_env=str(search_data.get("api_key_env", default.search.api_key_env)),
            timeout_seconds=float(search_data.get("timeout_seconds", default.search.timeout_seconds)),
        ),
        llm=ProviderConfig(
            name=str(llm_data.get("name", default.llm.name)),
            model=str(llm_data.get("model", default.llm.model)),
            timeout_seconds=float(llm_data.get("timeout_seconds", default.llm.timeout_seconds)),
        ),
        cache=CacheConfig(mode=cache_data.get("mode", default.cache.mode)),
        static_fetch_timeout_seconds=float(fetch_data.get("static_timeout_seconds", default.static_fetch_timeout_seconds)),
        browser_fallback_enabled=bool(fetch_data.get("browser_fallback_enabled", default.browser_fallback_enabled)),
    )
```

- [ ] **Step 3: Run config tests**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit models and config**

Run:

```bash
git add src/browsli/models.py src/browsli/config.py tests/test_config.py pyproject.toml
git commit -m "feat: add app config and core models"
```

---

### Task 3: Link Registry and HTML Extraction

**Files:**
- Create: `src/browsli/links.py`
- Create: `src/browsli/extractor.py`
- Test: `tests/test_links.py`
- Test: `tests/test_extractor.py`

- [ ] **Step 1: Write link registry tests**

Create `tests/test_links.py`:

```python
from browsli.links import LinkRegistry, unknown_link_tokens
from browsli.models import Link


def test_link_registry_numbers_links_stably() -> None:
    registry = LinkRegistry.from_raw_links([
        ("Docs", "https://example.com/docs"),
        ("Download", "https://example.com/download"),
    ])

    assert registry.links == (
        Link(1, "Docs", "https://example.com/docs"),
        Link(2, "Download", "https://example.com/download"),
    )
    assert registry.resolve(2).url == "https://example.com/download"


def test_unknown_link_tokens_are_detected() -> None:
    links = (Link(1, "One", "https://example.com/one"),)

    assert unknown_link_tokens("Open [1] and [2]", links) == {2}
```

- [ ] **Step 2: Write extractor tests**

Create `tests/test_extractor.py`:

```python
from browsli.extractor import HtmlExtractor


def test_extractor_resolves_relative_links() -> None:
    html = """
    <html><head><title>Example</title></head>
    <body><main><h1>Hello</h1><p>Read <a href="/docs">docs</a>.</p></main></body></html>
    """

    doc = HtmlExtractor().extract("https://example.com/start", html)

    assert doc.title == "Example"
    assert "Hello" in doc.text
    assert doc.links[0].text == "docs"
    assert doc.links[0].url == "https://example.com/docs"


def test_extractor_marks_js_dependent_empty_page() -> None:
    html = '<html><body><div id="root"></div><script src="/app.js"></script></body></html>'

    doc = HtmlExtractor().extract("https://example.com/app", html)

    assert doc.js_dependent is True
    assert doc.text == ""
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_links.py tests/test_extractor.py -v
```

Expected: FAIL with missing `browsli.links` and `browsli.extractor` modules.

- [ ] **Step 4: Implement link registry**

Create `src/browsli/links.py`:

```python
from __future__ import annotations

import re
from collections.abc import Iterable

from .models import Link

_LINK_TOKEN = re.compile(r"\[(\d+)]")


class LinkRegistry:
    def __init__(self, links: tuple[Link, ...]) -> None:
        self.links = links
        self._by_id = {link.id: link for link in links}

    @classmethod
    def from_raw_links(cls, raw_links: Iterable[tuple[str, str]]) -> "LinkRegistry":
        links: list[Link] = []
        seen: set[tuple[str, str]] = set()
        for text, url in raw_links:
            normalized_text = " ".join(text.split()) or url
            key = (normalized_text, url)
            if key in seen:
                continue
            seen.add(key)
            links.append(Link(len(links) + 1, normalized_text, url))
        return cls(tuple(links))

    def resolve(self, link_id: int) -> Link:
        return self._by_id[link_id]


def unknown_link_tokens(content: str, links: tuple[Link, ...]) -> set[int]:
    valid = {link.id for link in links}
    referenced = {int(match.group(1)) for match in _LINK_TOKEN.finditer(content)}
    return referenced - valid
```

- [ ] **Step 5: Implement HTML extractor**

Create `src/browsli/extractor.py`:

```python
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .links import LinkRegistry
from .models import ExtractedDocument


class HtmlExtractor:
    def extract(self, source_url: str, html: str) -> ExtractedDocument:
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        title = self._title(soup) or source_url
        body = soup.find("main") or soup.find("article") or soup.find("body") or soup
        text = "\n".join(line for line in (part.strip() for part in body.get_text("\n").splitlines()) if line)
        raw_links = [
            (anchor.get_text(" ", strip=True), urljoin(source_url, href))
            for anchor in body.find_all("a", href=True)
            if (href := anchor.get("href")) and not href.startswith(("javascript:", "mailto:", "tel:"))
        ]
        links = LinkRegistry.from_raw_links(raw_links).links
        js_dependent = not text and "<script" in html.lower()
        return ExtractedDocument(source_url=source_url, title=title, text=text, links=links, js_dependent=js_dependent)

    def _title(self, soup: BeautifulSoup) -> str:
        title = soup.find("title")
        if title is None:
            heading = soup.find(["h1", "h2"])
            return heading.get_text(" ", strip=True) if heading else ""
        return title.get_text(" ", strip=True)
```

- [ ] **Step 6: Run link and extractor tests**

Run:

```bash
uv run pytest tests/test_links.py tests/test_extractor.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit link extraction**

Run:

```bash
git add src/browsli/links.py src/browsli/extractor.py tests/test_links.py tests/test_extractor.py
git commit -m "feat: preserve extracted page links"
```

---

### Task 4: Provider Protocols, Transformer, and Link Safety

**Files:**
- Create: `src/browsli/providers/__init__.py`
- Create: `src/browsli/providers/base.py`
- Create: `src/browsli/transformer.py`
- Test: `tests/test_transformer.py`

- [ ] **Step 1: Write transformer tests**

Create `tests/test_transformer.py`:

```python
import pytest

from browsli.models import ExtractedDocument, Link, ProviderError
from browsli.transformer import Transformer


class FakeLLM:
    def __init__(self, content: str | ProviderError) -> None:
        self.content = content

    async def complete(self, prompt: str) -> str:
        if isinstance(self.content, ProviderError):
            raise self.content
        return self.content


@pytest.mark.asyncio
async def test_transformer_accepts_known_link_tokens() -> None:
    doc = ExtractedDocument(
        source_url="https://example.com",
        title="Example",
        text="Read docs.",
        links=(Link(1, "docs", "https://example.com/docs"),),
    )

    result = await Transformer(FakeLLM("Summary with docs [1]")).transform(doc)

    assert result.content == "Summary with docs [1]"
    assert result.transformed is True


@pytest.mark.asyncio
async def test_transformer_falls_back_when_llm_fails() -> None:
    doc = ExtractedDocument(
        source_url="https://example.com",
        title="Example",
        text="Readable extracted text",
        links=(),
    )

    result = await Transformer(FakeLLM(ProviderError("litellm", "api", "down"))).transform(doc)

    assert result.content == "Readable extracted text"
    assert result.transformed is False
    assert result.status == "litellm api: down"


@pytest.mark.asyncio
async def test_transformer_rejects_unknown_link_tokens() -> None:
    doc = ExtractedDocument(
        source_url="https://example.com",
        title="Example",
        text="Read docs.",
        links=(Link(1, "docs", "https://example.com/docs"),),
    )

    result = await Transformer(FakeLLM("Invented [2]")).transform(doc)

    assert result.content == "Read docs."
    assert result.transformed is False
    assert "unknown link token" in result.status
```

- [ ] **Step 2: Run transformer tests to verify they fail**

Run:

```bash
uv run pytest tests/test_transformer.py -v
```

Expected: FAIL with missing provider and transformer modules.

- [ ] **Step 3: Implement provider protocol**

Create `src/browsli/providers/base.py`:

```python
from __future__ import annotations

from typing import Protocol

from browsli.models import SearchResult


class LLMProvider(Protocol):
    async def complete(self, prompt: str) -> str: ...


class SearchProvider(Protocol):
    async def search(self, query: str) -> tuple[SearchResult, ...]: ...
```

Create `src/browsli/providers/__init__.py`:

```python
from .base import LLMProvider, SearchProvider

__all__ = ["LLMProvider", "SearchProvider"]
```

- [ ] **Step 4: Implement transformer**

Create `src/browsli/transformer.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from .links import unknown_link_tokens
from .models import ExtractedDocument, ProviderError
from .providers import LLMProvider


@dataclass(frozen=True, slots=True)
class TransformResult:
    content: str
    transformed: bool
    status: str = ""


class Transformer:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def transform(self, document: ExtractedDocument) -> TransformResult:
        prompt = self._prompt(document)
        try:
            content = await self._llm.complete(prompt)
        except ProviderError as error:
            return TransformResult(document.text, False, str(error))

        unknown = unknown_link_tokens(content, document.links)
        if unknown:
            return TransformResult(document.text, False, f"unknown link token rejected: {sorted(unknown)}")
        return TransformResult(content.strip(), True)

    def _prompt(self, document: ExtractedDocument) -> str:
        link_lines = "\n".join(f"[{link.id}] {link.text}: {link.url}" for link in document.links)
        return (
            "Condense this web document for terminal reading. Preserve key claims and meaningful links. "
            "Use only the numbered link tokens listed below; do not invent URLs or link numbers.\n\n"
            f"Title: {document.title}\nSource: {document.source_url}\n\n"
            f"Links:\n{link_lines}\n\nContent:\n{document.text}"
        )
```

- [ ] **Step 5: Run transformer tests**

Run:

```bash
uv run pytest tests/test_transformer.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit transformer boundary**

Run:

```bash
git add src/browsli/providers src/browsli/transformer.py tests/test_transformer.py
git commit -m "feat: add LLM transformation boundary"
```

---

### Task 5: Fetch Renderer and Provider Adapters

**Files:**
- Create: `src/browsli/fetch.py`
- Create: `src/browsli/providers/litellm_provider.py`
- Create: `src/browsli/providers/tavily_provider.py`
- Modify: `src/browsli/providers/__init__.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Extend config tests for missing API keys**

Append to `tests/test_config.py`:

```python
import pytest

from browsli.models import ProviderError


def test_provider_config_raises_clear_error_for_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    provider = ProviderConfig(name="tavily", api_key_env="TAVILY_API_KEY")

    with pytest.raises(ProviderError) as error:
        provider.require_api_key()

    assert error.value.category == "config"
    assert "TAVILY_API_KEY" in error.value.message
```

- [ ] **Step 2: Implement static and browser fetchers**

Create `src/browsli/fetch.py`:

```python
from __future__ import annotations

import httpx

from .models import ProviderError


class StaticFetcher:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def fetch(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.TimeoutException as error:
            raise ProviderError("http", "timeout", str(error)) from error
        except httpx.HTTPError as error:
            raise ProviderError("http", "network", str(error)) from error


class BrowserRenderer:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_milliseconds = int(timeout_seconds * 1000)

    async def fetch(self, url: str) -> str:
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise ProviderError("browser", "unsupported", "playwright is not installed") from error

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self._timeout_milliseconds)
                return await page.content()
            finally:
                await browser.close()
```

- [ ] **Step 3: Implement LiteLLM adapter**

Create `src/browsli/providers/litellm_provider.py`:

```python
from __future__ import annotations

import asyncio

import litellm

from browsli.config import ProviderConfig
from browsli.models import ProviderError


class LiteLLMProvider:
    def __init__(self, config: ProviderConfig) -> None:
        if config.model is None:
            raise ProviderError("litellm", "config", "missing llm model")
        self._model = config.model
        self._timeout = config.timeout_seconds

    async def complete(self, prompt: str) -> str:
        try:
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as error:
            raise ProviderError("litellm", "timeout", "LLM request timed out") from error
        except litellm.AuthenticationError as error:
            raise ProviderError("litellm", "auth", str(error)) from error
        except litellm.APIError as error:
            raise ProviderError("litellm", "api", str(error)) from error
        except Exception as error:
            raise ProviderError("litellm", "api", str(error)) from error

        content = response.choices[0].message.content
        return content or ""
```

- [ ] **Step 4: Implement Tavily adapter**

Create `src/browsli/providers/tavily_provider.py`:

```python
from __future__ import annotations

import asyncio

from tavily import TavilyClient

from browsli.config import ProviderConfig
from browsli.models import ProviderError, SearchResult


class TavilySearchProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self._api_key = config.require_api_key()
        self._timeout = config.timeout_seconds

    async def search(self, query: str) -> tuple[SearchResult, ...]:
        def run_search() -> dict:
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
```

- [ ] **Step 5: Export adapters**

Modify `src/browsli/providers/__init__.py`:

```python
from .base import LLMProvider, SearchProvider
from .litellm_provider import LiteLLMProvider
from .tavily_provider import TavilySearchProvider

__all__ = ["LLMProvider", "LiteLLMProvider", "SearchProvider", "TavilySearchProvider"]
```

- [ ] **Step 6: Run config tests**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit adapters**

Run:

```bash
git add src/browsli/fetch.py src/browsli/providers tests/test_config.py pyproject.toml
git commit -m "feat: add provider adapters"
```

---

### Task 6: Browser Session Navigation, Cache, and Error Documents

**Files:**
- Create: `src/browsli/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write session tests**

Create `tests/test_session.py`:

```python
import pytest

from browsli.models import ExtractedDocument, Link, ProviderError, SearchResult, DocumentKind
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
    session = BrowserSession(FakeSearch(), fetcher, None, FakeTransformer(), browser_fallback_enabled=False)

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
    session = BrowserSession(FakeSearch(), fetcher, None, FakeTransformer(), browser_fallback_enabled=False)

    await session.open_url("https://example.com/page")
    await session.open_url("https://example.com/page")

    assert fetcher.calls == 1


@pytest.mark.asyncio
async def test_search_failure_keeps_error_document_usable() -> None:
    session = BrowserSession(FailingSearch(), FakeFetcher(), None, FakeTransformer(), browser_fallback_enabled=False)

    doc = await session.search("python")

    assert doc.kind == DocumentKind.ERROR
    assert "tavily api: down" in doc.status
```

- [ ] **Step 2: Run session tests to verify they fail**

Run:

```bash
uv run pytest tests/test_session.py -v
```

Expected: FAIL with missing `browsli.session` module.

- [ ] **Step 3: Implement browser session**

Create `src/browsli/session.py`:

```python
from __future__ import annotations

from .extractor import HtmlExtractor
from .links import LinkRegistry
from .models import BrowserDocument, DocumentKind, ExtractedDocument, Link, ProviderError, SearchResult
from .providers import SearchProvider
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
            if extracted.js_dependent and self._browser_fallback_enabled and self._browser_fetcher is not None:
                html = await self._browser_fetcher.fetch(url)
                extracted = self._extractor.extract(url, html)
            elif extracted.js_dependent:
                doc = self._error_document("Unsupported JavaScript page", url, "browser fallback is disabled")
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
        link = next(link for link in self._current.links if link.id == link_id)
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

    async def _search_document(self, query: str, results: tuple[SearchResult, ...]) -> BrowserDocument:
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
        return BrowserDocument(kind=DocumentKind.ERROR, title=title, source=source, content=status, status=status)
```

- [ ] **Step 4: Run session tests**

Run:

```bash
uv run pytest tests/test_session.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit browser session**

Run:

```bash
git add src/browsli/session.py tests/test_session.py
git commit -m "feat: add browser session navigation"
```

---

### Task 7: Textual Application Shell

**Files:**
- Create: `src/browsli/app.py`
- Modify: `src/browsli/__init__.py`
- Test: `tests/test_app_smoke.py`

- [ ] **Step 1: Write Textual smoke test**

Create `tests/test_app_smoke.py`:

```python
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
```

- [ ] **Step 2: Run app smoke test to verify it fails**

Run:

```bash
uv run pytest tests/test_app_smoke.py -v
```

Expected: FAIL with missing `browsli.app` module.

- [ ] **Step 3: Implement Textual app**

Create `src/browsli/app.py`:

```python
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from .config import load_config
from .fetch import BrowserRenderer, StaticFetcher
from .models import BrowserDocument
from .providers import LiteLLMProvider, TavilySearchProvider
from .session import BrowserSession
from .transformer import Transformer


class BrowsliApp(App):
    CSS = """
    #address { dock: top; }
    #document { width: 2fr; padding: 1; }
    #links { width: 1fr; border-left: solid $accent; }
    """
    BINDINGS = [
        ("ctrl+p", "focus_address", "Command"),
        ("alt-left", "back", "Back"),
        ("alt-right", "forward", "Forward"),
    ]

    def __init__(self, session: BrowserSession | None = None) -> None:
        super().__init__()
        self._session = session or build_session()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(id="address")
        with Horizontal():
            yield Static(id="document")
            with Vertical(id="links"):
                yield Static("Links")
                yield ListView(id="link-list")
        yield Footer()

    def on_mount(self) -> None:
        if self._session.current is not None:
            self._render_document(self._session.current)
        else:
            self.query_one("#document", Static).update("Enter a search query or URL.")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        if value.startswith(("http://", "https://")):
            doc = await self._session.open_url(value)
        else:
            doc = await self._session.search(value)
        self._render_document(doc)

    async def action_back(self) -> None:
        self._render_document(await self._session.back())

    async def action_forward(self) -> None:
        self._render_document(await self._session.forward())

    def action_focus_address(self) -> None:
        self.query_one("#address", Input).focus()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        link_id = int(event.item.id.removeprefix("link-"))
        self._render_document(await self._session.open_link(link_id))

    def _render_document(self, document: BrowserDocument) -> None:
        status = f"\n\nStatus: {document.status}" if document.status else ""
        self.query_one("#document", Static).update(f"# {document.title}\n\n{document.content}{status}")
        link_list = self.query_one("#link-list", ListView)
        link_list.clear()
        for link in document.links:
            link_list.append(ListItem(Static(f"[{link.id}] {link.text}\n{link.url}"), id=f"link-{link.id}"))


def build_session() -> BrowserSession:
    config = load_config()
    llm = LiteLLMProvider(config.llm)
    search = TavilySearchProvider(config.search)
    transformer = Transformer(llm)
    static_fetcher = StaticFetcher(config.static_fetch_timeout_seconds)
    browser_fetcher = BrowserRenderer(config.static_fetch_timeout_seconds) if config.browser_fallback_enabled else None
    return BrowserSession(
        search,
        static_fetcher,
        browser_fetcher,
        transformer,
        browser_fallback_enabled=config.browser_fallback_enabled,
    )
```

- [ ] **Step 4: Implement console entry point**

Modify `src/browsli/__init__.py`:

```python
from __future__ import annotations

from .app import BrowsliApp


def main() -> None:
    BrowsliApp().run()
```

- [ ] **Step 5: Run app smoke test**

Run:

```bash
uv run pytest tests/test_app_smoke.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Textual shell**

Run:

```bash
git add src/browsli/app.py src/browsli/__init__.py tests/test_app_smoke.py
git commit -m "feat: add Textual browser shell"
```

---

### Task 8: End-to-End Test Sweep and Acceptance Verification

**Files:**
- Modify only files required to fix failures found by this task.

- [ ] **Step 1: Run the normal test suite**

Run:

```bash
uv run pytest -v
```

Expected: PASS for all tests without live Tavily or LiteLLM calls.

- [ ] **Step 2: Run the console command help check**

Run:

```bash
uv run browsli --help
```

Expected: either Textual handles the command by launching the app or the command exits with Textual help behavior. If it launches the app in the terminal, exit with `ctrl+c` and record that command execution reaches the Textual entry point.

- [ ] **Step 3: Verify provider behavior remains behind adapters**

Inspect these files only:

- `src/browsli/app.py`
- `src/browsli/session.py`
- `src/browsli/providers/litellm_provider.py`
- `src/browsli/providers/tavily_provider.py`

Required result:

- `src/browsli/app.py` imports provider adapters only inside `build_session()`.
- `src/browsli/session.py` imports only provider protocols, not LiteLLM or Tavily.
- LiteLLM imports appear only in `src/browsli/providers/litellm_provider.py`.
- Tavily imports appear only in `src/browsli/providers/tavily_provider.py`.

- [ ] **Step 4: Commit verification fixes if any**

If Step 1 or Step 3 required changes, run:

```bash
git add src tests pyproject.toml
git commit -m "fix: complete Browsli MVP verification"
```

If no files changed, do not create an empty commit.

---

## Self-Review Notes

Spec coverage:

- Textual TUI: Task 7.
- Browser-like back/forward plus command/address input: Tasks 6 and 7.
- Search provider adapter: Tasks 4, 5, and 6.
- URL browsing and static fetch default: Tasks 5 and 6.
- Config-gated browser fallback: Tasks 2, 5, and 6.
- LLM condensation via LiteLLM adapter: Tasks 4 and 5.
- Numbered/selectable links: Tasks 3, 6, and 7.
- In-memory cache: Task 6.
- TOML config and environment API keys: Tasks 1, 2, and 5.
- Provider/network/extraction/LLM/config failures as UI states: Tasks 2, 4, 5, 6, and 7.
- Tests without live provider calls: Tasks 1 through 8.

Type consistency:

- Provider interfaces are `LLMProvider.complete(prompt)` and `SearchProvider.search(query)`.
- Navigation API is `search(query)`, `open_url(url)`, `open_link(id)`, `back()`, and `forward()`.
- Document models consistently use `BrowserDocument`, `ExtractedDocument`, `SearchResult`, and `Link`.
