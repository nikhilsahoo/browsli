from __future__ import annotations

from browsli.config import ProviderConfig
from browsli.models import ProviderError

from .base import LLMProvider


def build_llm_provider(config: ProviderConfig) -> LLMProvider:
    if config.name == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(config)
    if config.name == "ollama-cloud":
        from .ollama_provider import OllamaCloudProvider

        return OllamaCloudProvider(config)
    if config.name == "codex":
        raise ProviderError(
            "codex",
            "unsupported",
            "Codex and ChatGPT subscriptions are not API credentials. "
            "Use the openai provider with an OPENAI_API_KEY instead.",
        )
    raise ProviderError("llm", "config", f"unknown LLM provider: {config.name}")

