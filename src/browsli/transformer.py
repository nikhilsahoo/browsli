from __future__ import annotations

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
        prompt = self._prompt(document)
        try:
            content = await self._llm.complete(prompt)
        except ProviderError as error:
            return TransformResult(document.text, False, str(error))

        unknown = unknown_link_tokens(content, document.links)
        if unknown:
            return TransformResult(document.text, False, f"unknown link token rejected: {sorted(unknown)}")
        return TransformResult(content.strip(), True)

    def _prompt(self, document: ExtractedDocument) -> str:
        link_lines = "\n".join(f"[{link.id}] {link.text}: {link.url}" for link in document.links)
        return (
            "Condense this web document for terminal reading. Preserve key claims and meaningful links. "
            "Use only the numbered link tokens listed below; do not invent URLs or link numbers.\n\n"
            f"Title: {document.title}\nSource: {document.source_url}\n\n"
            f"Links:\n{link_lines}\n\nContent:\n{document.text}"
        )

