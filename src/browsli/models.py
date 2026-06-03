from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class DocumentKind(str, Enum):
    SEARCH = "search"
    PAGE = "page"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Link:
    id: int
    text: str
    url: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    source_url: str
    title: str
    text: str
    links: tuple[Link, ...]
    js_dependent: bool = False


@dataclass(frozen=True, slots=True)
class BrowserDocument:
    kind: DocumentKind
    title: str
    source: str
    content: str
    links: tuple[Link, ...] = field(default_factory=tuple)
    transformed: bool = True
    status: str = ""


@dataclass(frozen=True, slots=True)
class ProviderError(Exception):
    provider: str
    category: Literal["config", "auth", "timeout", "network", "api", "unsupported"]
    message: str

    def __str__(self) -> str:
        return f"{self.provider} {self.category}: {self.message}"

