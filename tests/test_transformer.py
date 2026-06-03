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

