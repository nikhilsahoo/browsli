import pytest

from browsli.config import ProviderConfig
from browsli.models import ProviderError
from browsli.providers.factory import build_llm_provider
from browsli.providers.ollama_provider import OllamaCloudProvider
from browsli.providers.openai_provider import OpenAIProvider


class FakeOpenAIResponses:
    def __init__(self) -> None:
        self.calls = []

    async def create(self, *, model: str, input: str):
        self.calls.append({"model": model, "input": input})

        class Response:
            output_text = "openai text"

        return Response()

    def stream(self, *, model: str, input: str):
        self.calls.append({"model": model, "input": input, "stream": True})

        class Event:
            def __init__(self, delta: str) -> None:
                self.type = "response.output_text.delta"
                self.delta = delta

        class Stream:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def __aiter__(self):
                yield Event("open")
                yield Event("ai")

        return Stream()


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeOpenAIResponses()


class FailingOpenAIResponses:
    async def create(self, *, model: str, input: str):
        raise RuntimeError("boom")


class FailingOpenAIClient:
    def __init__(self) -> None:
        self.responses = FailingOpenAIResponses()


class FakeOllamaClient:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, *, model: str, messages: list[dict[str, str]], stream: bool):
        self.calls.append({"model": model, "messages": messages, "stream": stream})
        if stream:
            async def chunks():
                yield {"message": {"content": "ollama"}}
                yield {"message": {"content": " stream"}}

            return chunks()
        return {"message": {"content": "ollama text"}}


@pytest.mark.asyncio
async def test_openai_provider_uses_responses_api(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    client = FakeOpenAIClient()
    provider = OpenAIProvider(
        ProviderConfig(name="openai", api_key_env="OPENAI_API_KEY", model="gpt-4o-mini"),
        client=client,
    )

    assert await provider.complete("Summarize") == "openai text"
    assert client.responses.calls == [{"model": "gpt-4o-mini", "input": "Summarize"}]


@pytest.mark.asyncio
async def test_openai_provider_streams_responses_api_text(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    client = FakeOpenAIClient()
    provider = OpenAIProvider(
        ProviderConfig(name="openai", api_key_env="OPENAI_API_KEY", model="gpt-4o-mini"),
        client=client,
    )

    assert [chunk async for chunk in provider.stream_complete("Summarize")] == ["open", "ai"]
    assert client.responses.calls[-1] == {
        "model": "gpt-4o-mini",
        "input": "Summarize",
        "stream": True,
    }


@pytest.mark.asyncio
async def test_openai_provider_wraps_unexpected_client_errors(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    provider = OpenAIProvider(
        ProviderConfig(name="openai", api_key_env="OPENAI_API_KEY", model="gpt-4o-mini"),
        client=FailingOpenAIClient(),
    )

    with pytest.raises(ProviderError) as error:
        await provider.complete("Summarize")

    assert error.value.provider == "openai"
    assert error.value.category == "api"
    assert "boom" in error.value.message


@pytest.mark.asyncio
async def test_ollama_cloud_provider_uses_native_client(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    client = FakeOllamaClient()
    provider = OllamaCloudProvider(
        ProviderConfig(name="ollama-cloud", api_key_env="OLLAMA_API_KEY", model="gpt-oss:120b"),
        client=client,
    )

    assert await provider.complete("Summarize") == "ollama text"
    assert client.calls == [
        {
            "model": "gpt-oss:120b",
            "messages": [{"role": "user", "content": "Summarize"}],
            "stream": False,
        }
    ]


@pytest.mark.asyncio
async def test_ollama_cloud_provider_streams_native_chat(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    client = FakeOllamaClient()
    provider = OllamaCloudProvider(
        ProviderConfig(name="ollama-cloud", api_key_env="OLLAMA_API_KEY", model="gpt-oss:120b"),
        client=client,
    )

    assert [chunk async for chunk in provider.stream_complete("Summarize")] == [
        "ollama",
        " stream",
    ]
    assert client.calls[-1] == {
        "model": "gpt-oss:120b",
        "messages": [{"role": "user", "content": "Summarize"}],
        "stream": True,
    }


def test_llm_factory_rejects_codex_subscription_provider() -> None:
    config = ProviderConfig(name="codex", api_key_env=None, model="codex")

    with pytest.raises(ProviderError) as error:
        build_llm_provider(config)

    assert error.value.category == "unsupported"
    assert "Codex" in error.value.message
    assert "OPENAI_API_KEY" in error.value.message


def test_llm_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ProviderError) as error:
        build_llm_provider(ProviderConfig(name="unknown", model="model"))

    assert error.value.category == "config"
    assert "unknown LLM provider" in error.value.message
