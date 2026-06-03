from __future__ import annotations

import asyncio

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
)

from browsli.config import ProviderConfig
from browsli.models import ProviderError


class OpenAIProvider:
    def __init__(self, config: ProviderConfig, *, client: object | None = None) -> None:
        if config.model is None:
            raise ProviderError("openai", "config", "missing llm model")
        self._model = config.model
        self._timeout = config.timeout_seconds
        self._client = client or AsyncOpenAI(
            api_key=config.require_api_key(),
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )

    async def complete(self, prompt: str) -> str:
        try:
            response = await asyncio.wait_for(
                self._client.responses.create(model=self._model, input=prompt),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as error:
            raise ProviderError("openai", "timeout", "LLM request timed out") from error
        except AuthenticationError as error:
            raise ProviderError("openai", "auth", str(error)) from error
        except APITimeoutError as error:
            raise ProviderError("openai", "timeout", str(error)) from error
        except APIConnectionError as error:
            raise ProviderError("openai", "network", str(error)) from error
        except APIError as error:
            raise ProviderError("openai", "api", str(error)) from error
        except OpenAIError as error:
            raise ProviderError("openai", "api", str(error)) from error
        except Exception as error:
            raise ProviderError("openai", "api", str(error)) from error

        return str(getattr(response, "output_text", "") or "")
