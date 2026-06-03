from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .links import unknown_link_tokens
from .models import ExtractedDocument, ProviderError
from .providers import LLMProvider


@dataclass(frozen=True, slots=True)
class TransformResult:
    content: str
    transformed: bool
    status: str = ""


class Transformer:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def transform(self, document: ExtractedDocument) -> TransformResult:
        result: TransformResult | None = None
        async for chunk in self.stream_transform(document):
            result = chunk
        return result or TransformResult("", True)

    async def stream_transform(self, document: ExtractedDocument) -> AsyncIterator[TransformResult]:
        prompt = self._prompt(document)
        content = ""
        try:
            async for chunk in self._stream_complete(prompt):
                content += chunk
                yield TransformResult(content, True)
        except ProviderError as error:
            yield TransformResult(document.text, False, str(error))
            return

        unknown = unknown_link_tokens(content, document.links)
        if unknown:
            yield TransformResult(document.text, False, f"unknown link token rejected: {sorted(unknown)}")
            return
        if not content:
            yield TransformResult("", True)
        elif content != content.strip():
            yield TransformResult(content.strip(), True)

    async def _stream_complete(self, prompt: str) -> AsyncIterator[str]:
        if hasattr(self._llm, "stream_complete"):
            async for chunk in self._llm.stream_complete(prompt):
                yield chunk
            return
        yield await self._llm.complete(prompt)

    def _prompt(self, document: ExtractedDocument) -> str:
        link_lines = "\n".join(f"[{link.id}] {link.text}: {link.url}" for link in document.links)
        return (
            "Render this web document for terminal reading with high factual fidelity. "
            "Preserve concrete facts, step-by-step instructions, examples, tables, and meaningful links. "
            "Preserve code blocks verbatim, including language labels, indentation, and complete contents. "
            "Do not replace code, commands, data, or examples with a prose summary. "
            "Use only the numbered link tokens listed below; do not invent URLs or link numbers.\n\n"
            f"Title: {document.title}\nSource: {document.source_url}\n\n"
            f"Links:\n{link_lines}\n\nContent:\n{document.text}"
        )

