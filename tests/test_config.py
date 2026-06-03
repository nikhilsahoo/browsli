import pytest

from browsli.config import AppConfig, ProviderConfig, load_config
from browsli.models import ProviderError


def test_default_config_values() -> None:
    config = AppConfig.default()

    assert config.search.name == "tavily"
    assert config.llm.name == "openai"
    assert config.llm.api_key_env == "OPENAI_API_KEY"
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


def test_ollama_cloud_config_defaults_to_ollama_api_key() -> None:
    from pathlib import Path

    config_path = Path(".codex-test-config.toml")
    try:
        config_path.write_text(
            """
            [llm]
            name = "ollama-cloud"
            model = "gpt-oss:120b"
            """,
            encoding="utf-8",
        )

        config = load_config(config_path)

        assert config.llm.api_key_env == "OLLAMA_API_KEY"
    finally:
        config_path.unlink(missing_ok=True)


def test_load_config_accepts_utf8_bom_file() -> None:
    from pathlib import Path

    config_path = Path(".codex-test-config-bom.toml")
    try:
        config_path.write_text(
            """
            [llm]
            name = "ollama-cloud"
            model = "gemma4:31b-cloud"
            api_key_env = "OLLAMA_API_KEY"
            """,
            encoding="utf-8-sig",
        )

        config = load_config(config_path)

        assert config.llm.name == "ollama-cloud"
        assert config.llm.model == "gemma4:31b-cloud"
    finally:
        config_path.unlink(missing_ok=True)
