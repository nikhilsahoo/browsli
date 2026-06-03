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
        code_blocks = self._replace_code_blocks(body)
        text = "\n".join(
            line for line in (part.strip() for part in body.get_text("\n").splitlines()) if line
        )
        for placeholder, block in code_blocks.items():
            text = text.replace(placeholder, block)
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

    def _replace_code_blocks(self, body) -> dict[str, str]:
        blocks: dict[str, str] = {}
        for index, pre in enumerate(body.find_all("pre"), start=1):
            code = pre.find("code")
            source = code or pre
            code_text = source.get_text("\n", strip=False).strip("\n")
            if not code_text.strip():
                continue

            language = self._code_language(code)
            placeholder = f"BROWSLI_CODE_BLOCK_{index}"
            fence = f"```{language}\n{code_text.rstrip()}\n```"
            blocks[placeholder] = fence
            pre.replace_with(f"\n{placeholder}\n")
        return blocks

    def _code_language(self, code) -> str:
        if code is None:
            return ""
        classes = code.get("class", [])
        for class_name in classes:
            if class_name.startswith("language-"):
                return class_name.removeprefix("language-")
            if class_name.startswith("lang-"):
                return class_name.removeprefix("lang-")
        return ""

