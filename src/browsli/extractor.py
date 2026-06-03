from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .links import LinkRegistry
from .models import ExtractedDocument


class HtmlExtractor:
    def extract(self, source_url: str, html: str) -> ExtractedDocument:
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        title = self._title(soup) or source_url
        body = soup.find("main") or soup.find("article") or soup.find("body") or soup
        text = "\n".join(
            line for line in (part.strip() for part in body.get_text("\n").splitlines()) if line
        )
        raw_links = [
            (anchor.get_text(" ", strip=True), urljoin(source_url, href))
            for anchor in body.find_all("a", href=True)
            if (href := anchor.get("href")) and not href.startswith(("javascript:", "mailto:", "tel:"))
        ]
        links = LinkRegistry.from_raw_links(raw_links).links
        js_dependent = not text and "<script" in html.lower()
        return ExtractedDocument(
            source_url=source_url,
            title=title,
            text=text,
            links=links,
            js_dependent=js_dependent,
        )

    def _title(self, soup: BeautifulSoup) -> str:
        title = soup.find("title")
        if title is None:
            heading = soup.find(["h1", "h2"])
            return heading.get_text(" ", strip=True) if heading else ""
        return title.get_text(" ", strip=True)

