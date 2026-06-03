from .base import LLMProvider, SearchProvider

__all__ = ["LLMProvider", "LiteLLMProvider", "SearchProvider", "TavilySearchProvider"]


def __getattr__(name: str) -> object:
    if name == "LiteLLMProvider":
        from .litellm_provider import LiteLLMProvider

        return LiteLLMProvider
    if name == "TavilySearchProvider":
        from .tavily_provider import TavilySearchProvider

        return TavilySearchProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
