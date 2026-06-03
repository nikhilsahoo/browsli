from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ollama import AsyncClient, RequestError, ResponseError

from browsli.config import ProviderConfig
from browsli.models import ProviderError


class OllamaCloudProvider:
    def __init__(self, config: ProviderConfig, *, client: object | None = None) -> None:
        if config.model is None:
            raise ProviderError("ollama-cloud", "config", "missing llm model")
        self._model = config.model
        self._timeout = config.timeout_seconds
        self._client = client or AsyncClient(
            host=config.base_url or "https://ollama.com",
            headers={"Authorization": f"Bearer {config.require_api_key()}"},
            timeout=config.timeout_seconds,
        )

    async def complete(self, prompt: str) -> str:
        try:
            response = await asyncio.wait_for(
                self._client.chat(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as error:
            raise ProviderError("ollama-cloud", "timeout", "LLM request timed out") from error
        except ResponseError as error:
            raise ProviderError("ollama-cloud", "api", str(error)) from error
        except RequestError as error:
            raise ProviderError("ollama-cloud", "network", str(error)) from error
        except Exception as error:
            raise ProviderError("ollama-cloud", "api", str(error)) from error

        message = response.get("message", {})
        return str(message.get("content", "") or "")

    async def stream_complete(self, prompt: str) -> AsyncIterator[str]:
        try:
            async with asyncio.timeout(self._timeout):
                stream = await self._client.chat(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                )
                async for chunk in stream:
                    message = chunk.get("message", {})
                    content = str(message.get("content", "") or "")
                    if content:
                        yield content
        except TimeoutError as error:
            raise ProviderError("ollama-cloud", "timeout", "LLM request timed out") from error
        except ResponseError as error:
            raise ProviderError("ollama-cloud", "api", str(error)) from error
        except RequestError as error:
            raise ProviderError("ollama-cloud", "network", str(error)) from error
        except Exception as error:
            raise ProviderError("ollama-cloud", "api", str(error)) from error

