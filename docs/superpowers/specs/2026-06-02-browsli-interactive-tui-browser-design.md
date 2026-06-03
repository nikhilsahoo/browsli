# Browsli Interactive TUI Browser Design

## Purpose

Browsli is an interactive terminal browser for search and web browsing. Instead of rendering HTML, it fetches search results and webpages, extracts their meaning and links, and uses an LLM to produce readable condensed text while keeping all navigable hyperlinks grounded in the original search result or page content.

The MVP treats search and browsing as equally important. Notes, persistent history, and source-tracking/citation workflows are deferred to later MVPs.

## Project Context

The repository is a new Python 3.12 package named `browsli` with a console script entry point. It currently contains only a minimal `main()` and no committed history. The design should establish clean boundaries before implementation rather than building provider logic directly into the UI.

## MVP Scope

The MVP includes:

- A Textual-based TUI.
- A browser-like navigation stack with back and forward.
- A command palette for search, open URL, back, forward, and link-jump actions.
- Search through a configurable provider adapter.
- Page browsing by URL.
- Static HTML fetch as the default page retrieval path.
- Optional browser-render fallback when enabled in config.
- LLM-based readable condensation of search results and page content.
- Numbered links plus keyboard-selectable anchors.
- In-memory caching for transformed documents during one app session.
- TOML config for non-secret settings and environment variables for API keys.
- Tests for parsing, link preservation, navigation, cache behavior, provider boundaries, and error states.

Deferred:

- Notes.
- Persistent history.
- Source-tracking/citation workflows beyond preserving navigable URLs.
- Persistent disk cache.
- Full document graph/index.
- Interactive setup command.

## Architecture

The app should have a small browser core independent of Textual. Textual owns presentation and input. The browser core owns navigation, document state, provider orchestration, link identity, and cache behavior.

Core units:

- `BrowserSession`: owns the current document, back/forward stacks, active URL/query, and in-memory cache. Public operations include `search(query)`, `open_url(url)`, `open_link(id)`, `back()`, and `forward()`.
- `SearchProvider`: app interface for search queries. The first implementation is a Tavily-backed adapter.
- `FetchRenderer`: retrieves page content. It fetches static HTML by default and uses a browser-render fallback only when enabled in config.
- `Extractor`: converts fetched or rendered content into normalized text blocks plus discovered hyperlinks.
- `LLMProvider`: app interface for text generation. The first implementation is a LiteLLM-backed adapter.
- `Transformer`: asks the LLM to produce readable condensation while preserving key claims and meaningful links.
- `LinkRegistry`: assigns stable numeric link IDs for the current transformed document and maps IDs to URLs and link text.
- `TextualApp`: renders the search/address input, document view, link/status areas, and command palette.

The Textual app must not fetch HTML, call LLM providers, parse links, or mutate navigation stacks directly. It calls the browser session API and renders returned state.

## Provider and Package Strategy

Browsli should not rebuild provider plumbing.

### LLM

Use LiteLLM behind `LLMProvider`.

LiteLLM provides a unified OpenAI-style interface for many model providers, including OpenAI, Anthropic, Gemini/Vertex, Bedrock, Azure, and Ollama, and normalizes many provider errors. Browsli config should specify a LiteLLM model string such as `openai/gpt-4o-mini`, `anthropic/...`, or `ollama/...`.

The rest of the app should not depend on LiteLLM response objects. The adapter returns app-level response models.

### Search

Use Tavily as the MVP search provider behind `SearchProvider`.

Tavily is a good first default because it targets AI/web-search workflows and offers Python support. The adapter should normalize provider results into app-level search result models containing title, snippet, and URL.

Future adapters can support Brave Search or SerpAPI without changing `BrowserSession` or Textual UI code.

### Avoid LangChain as App Core

LangChain has broad integrations, but Browsli does not need an agent framework as its core. The hard parts are terminal navigation, deterministic URL ownership, link preservation, and browser session state. If a LangChain integration is ever useful, it should remain isolated behind a provider adapter.

## Data Flow

### Search Flow

1. The user enters a query in the address/search bar or command palette.
2. `BrowserSession.search(query)` calls the configured `SearchProvider`.
3. Search results are normalized into a synthetic document containing title, snippet, source URL, and numbered/selectable result links.
4. The synthetic search document is passed through the transformer so results can be condensed without changing URLs.
5. Opening a result calls `BrowserSession.open_url(url)` and pushes the prior document onto the back stack.

### Page Flow

1. `BrowserSession.open_url(url)` checks the in-memory cache.
2. On a cache miss, `FetchRenderer` fetches static HTML first.
3. If extraction fails or content is clearly JavaScript-dependent, the app shows an unsupported/fallback status unless browser fallback is enabled in config.
4. `Extractor` emits normalized blocks and a raw link table.
5. `Transformer` condenses the content and references links through stable link tokens. It may summarize, reorder, or explain content, but it may not invent URLs.
6. `LinkRegistry` assigns `[1]`, `[2]`, etc. and exposes the same entries as keyboard-selectable anchors in the TUI.
7. Selecting a link calls `BrowserSession.open_link(id)`, resolves the URL from `LinkRegistry`, and opens it through the normal page flow.

The LLM is never the source of truth for URLs. URLs come from search results or extracted page links.

## Hyperlink Preservation

The MVP uses both inline numbered references and keyboard-selectable anchors.

- Inline transformed text contains markers such as `[1]` and `[2]`.
- A link list/status area maps numbers to normalized URLs and original or extracted link text.
- Keyboard navigation can focus and open link anchors from the document view or link list.
- Unknown link tokens in LLM output are rejected or repaired before display.
- Relative URLs are resolved against the source page URL during extraction, before LLM transformation.

## Content Transformation

The MVP transformation mode is readable condensation.

For each search-results document or page document, the transformer should preserve:

- Main topic and purpose.
- Key claims, instructions, facts, or decisions.
- Meaningful links and their relationship to the surrounding content.
- Enough source context for the user to decide whether to follow links.

The transformer should remove or reduce:

- Repeated navigation chrome.
- Boilerplate footer/header content.
- Cookie banners and unrelated site furniture.
- Duplicate text.

If the LLM fails but extraction succeeded, Browsli should display extracted readable text and mark it as untransformed.

## Configuration and Credentials

Use TOML config for non-secret settings and environment variables for API keys.

Config should cover:

- Search provider name, default `tavily`.
- LLM provider adapter name, default `litellm`.
- LiteLLM model string.
- Static fetch timeout.
- LLM timeout.
- Search timeout.
- Browser-render fallback enabled/disabled.
- Cache behavior, default in-memory only.

Secrets should come from environment variables, for example:

- `TAVILY_API_KEY` for Tavily.
- Provider-specific LiteLLM environment variables, such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or other provider keys required by the chosen model.

Missing required config or environment variables should produce explicit startup or first-use errors.

## Navigation Model

The MVP uses a hybrid model:

- Browser-like stack: open links, back, forward, address/search bar, reload if implemented during planning.
- Command palette: search, open URL, jump to link by number, back, forward, and help.

Back and forward operate over documents, including search result documents and page documents.

## Caching

Use in-memory cache only for MVP.

The cache should avoid repeated fetch/extract/transform work for the same URL during one app session. It should not persist across process restarts. Search-result caching may be included only if it naturally fits the same cache abstraction; page caching is the priority.

## Error Handling and Reliability

Provider and network failures are UI states, not terminal crashes.

Required behavior:

- Missing config or API key: show a clear startup or first-use error naming the missing setting or environment variable.
- Search provider failure: keep the current document visible and show a status message with provider name and failure category.
- Fetch failure: display an error document for that URL; retry and back navigation remain available.
- Extraction failure: display an unsupported-page document; if browser fallback is enabled, offer or use fallback.
- LLM failure: show extracted readable text if available, mark it as untransformed, and keep links traversable.
- Link mismatch: reject or repair transformed output that references unknown link tokens.
- Timeout: provider operations must be bounded; cancellation returns control to the TUI.

Reliability rule: fetched/extracted URLs remain the deterministic source of truth. The LLM cannot create navigable destinations.

## Testing Strategy

Normal tests should not call live providers. Use fake provider implementations at adapter boundaries.

Test coverage should include:

- URL and link extraction.
- Relative URL resolution.
- `LinkRegistry` stable numbering.
- Unknown link token rejection or repair.
- Keyboard-selectable link metadata.
- `BrowserSession` search, open, open link, back, and forward behavior.
- In-memory cache hits.
- Missing API key/config behavior.
- Search provider failure.
- Fetch failure.
- Extraction failure.
- LLM failure fallback to extracted text.
- Unsupported JavaScript-heavy content when browser fallback is disabled.
- Textual smoke test that launches the app and renders the main panes/status without provider calls.

Optional live-provider tests may be separate and explicitly opt-in through environment variables.

## MVP Acceptance Criteria

The MVP is complete when:

- A user can search, view condensed search results, open a result, read a condensed page, follow a link, and use back/forward navigation.
- Hyperlinks are numbered and keyboard-selectable.
- Navigable URLs are derived only from search results or extracted page links.
- Non-secret provider settings are configurable in TOML.
- API keys are read from environment variables.
- LiteLLM and Tavily are used through adapters rather than embedded in UI logic.
- Static HTML fetch is the default page retrieval path.
- Browser-render fallback is config-gated.
- In-memory page cache prevents repeated work within one session.
- Provider, network, extraction, LLM, and configuration failures are represented as usable UI states.
- The normal test suite verifies parsing/link preservation/navigation/cache/error behavior without live provider calls.
