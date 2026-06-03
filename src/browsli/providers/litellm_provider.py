from __future__ import annotations

import asyncio

import litellm

from browsli.config import ProviderConfig
from browsli.models import ProviderError


class LiteLLMProvider:
    def __init__(self, config: ProviderConfig) -> None:
        if config.model is None:
            raise ProviderError("litellm", "config", "missing llm model")
        self._model = config.model
        self._timeout = config.timeout_seconds

    async def complete(self, prompt: str) -> str:
        try:
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as error:
            raise ProviderError("litellm", "timeout", "LLM request timed out") from error
        except litellm.AuthenticationError as error:
            raise ProviderError("litellm", "auth", str(error)) from error
        except litellm.APIError as error:
            raise ProviderError("litellm", "api", str(error)) from error
        except Exception as error:
            raise ProviderError("litellm", "api", str(error)) from error

        content = response.choices[0].message.content
        return content or ""

