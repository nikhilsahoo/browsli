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
    def default(cls) -> AppConfig:
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
            api_key_env=_optional_str(search_data.get("api_key_env", default.search.api_key_env)),
            timeout_seconds=float(search_data.get("timeout_seconds", default.search.timeout_seconds)),
        ),
        llm=ProviderConfig(
            name=str(llm_data.get("name", default.llm.name)),
            model=_optional_str(llm_data.get("model", default.llm.model)),
            timeout_seconds=float(llm_data.get("timeout_seconds", default.llm.timeout_seconds)),
        ),
        cache=CacheConfig(mode=cache_data.get("mode", default.cache.mode)),
        static_fetch_timeout_seconds=float(
            fetch_data.get("static_timeout_seconds", default.static_fetch_timeout_seconds)
        ),
        browser_fallback_enabled=bool(
            fetch_data.get("browser_fallback_enabled", default.browser_fallback_enabled)
        ),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)

