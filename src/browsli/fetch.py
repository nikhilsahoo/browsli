from __future__ import annotations

import httpx

from .models import ProviderError


class StaticFetcher:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def fetch(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, follow_redirects=True
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.TimeoutException as error:
            raise ProviderError("http", "timeout", str(error)) from error
        except httpx.HTTPError as error:
            raise ProviderError("http", "network", str(error)) from error


class BrowserRenderer:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_milliseconds = int(timeout_seconds * 1000)

    async def fetch(self, url: str) -> str:
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise ProviderError("browser", "unsupported", "playwright is not installed") from error

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self._timeout_milliseconds)
                return await page.content()
            finally:
                await browser.close()

