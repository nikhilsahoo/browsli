import pytest

from browsli.config import AppConfig, ProviderConfig
from browsli.models import ProviderError


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


def test_provider_config_raises_clear_error_for_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    provider = ProviderConfig(name="tavily", api_key_env="TAVILY_API_KEY")

    with pytest.raises(ProviderError) as error:
        provider.require_api_key()

    assert error.value.category == "config"
    assert "TAVILY_API_KEY" in error.value.message
