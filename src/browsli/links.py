from __future__ import annotations

import re
from collections.abc import Iterable

from .models import Link

_LINK_TOKEN = re.compile(r"\[(\d+)]")


class LinkRegistry:
    def __init__(self, links: tuple[Link, ...]) -> None:
        self.links = links
        self._by_id = {link.id: link for link in links}

    @classmethod
    def from_raw_links(cls, raw_links: Iterable[tuple[str, str]]) -> LinkRegistry:
        links: list[Link] = []
        seen: set[tuple[str, str]] = set()
        for text, url in raw_links:
            normalized_text = " ".join(text.split()) or url
            key = (normalized_text, url)
            if key in seen:
                continue
            seen.add(key)
            links.append(Link(len(links) + 1, normalized_text, url))
        return cls(tuple(links))

    def resolve(self, link_id: int) -> Link:
        return self._by_id[link_id]


def unknown_link_tokens(content: str, links: tuple[Link, ...]) -> set[int]:
    valid = {link.id for link in links}
    referenced = {int(match.group(1)) for match in _LINK_TOKEN.finditer(content)}
    return referenced - valid

