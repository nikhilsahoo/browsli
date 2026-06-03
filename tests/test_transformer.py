import pytest

from browsli.models import ExtractedDocument, Link, ProviderError
from browsli.transformer import Transformer


class FakeLLM:
    def __init__(self, content: str | ProviderError) -> None:
        self.content = content
        self.prompt = ""

    async def complete(self, prompt: str) -> str:
        self.prompt = prompt
        if isinstance(self.content, ProviderError):
            raise self.content
        return self.content


class StreamingFakeLLM:
    async def stream_complete(self, prompt: str):
        yield "First"
        yield " second"


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

    result = await Transformer(FakeLLM(ProviderError("openai", "api", "down"))).transform(doc)

    assert result.content == "Readable extracted text"
    assert result.transformed is False
    assert result.status == "openai api: down"


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


@pytest.mark.asyncio
async def test_transformer_prompt_requires_verbatim_code_preservation() -> None:
    llm = FakeLLM("```python\ndef fibonacci(n):\n    return []\n```")
    doc = ExtractedDocument(
        source_url="https://example.com/fibonacci",
        title="Fibonacci",
        text="```python\ndef fibonacci(n):\n    return []\n```",
        links=(),
    )

    await Transformer(llm).transform(doc)

    assert "Preserve code blocks verbatim" in llm.prompt
    assert "Do not replace code" in llm.prompt
    assert "def fibonacci(n):" in llm.prompt


@pytest.mark.asyncio
async def test_transformer_streams_incremental_content() -> None:
    doc = ExtractedDocument(
        source_url="https://example.com",
        title="Example",
        text="Readable text",
        links=(),
    )

    chunks = [chunk async for chunk in Transformer(StreamingFakeLLM()).stream_transform(doc)]

    assert [chunk.content for chunk in chunks] == ["First", "First second"]
    assert chunks[-1].transformed is True

