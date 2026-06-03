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
