from .base import LLMProvider, SearchProvider
from .factory import build_llm_provider

__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "OllamaCloudProvider",
    "SearchProvider",
    "TavilySearchProvider",
    "build_llm_provider",
]


def __getattr__(name: str) -> object:
    if name == "OpenAIProvider":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider
    if name == "OllamaCloudProvider":
        from .ollama_provider import OllamaCloudProvider

        return OllamaCloudProvider
    if name == "TavilySearchProvider":
        from .tavily_provider import TavilySearchProvider

        return TavilySearchProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
