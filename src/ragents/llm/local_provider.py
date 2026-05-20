"""Ollama / vLLM local provider."""

from __future__ import annotations

from typing import Any

import requests

from ragents.errors import LLMError, LLMTimeoutError
from ragents.llm.base import LLMProvider
from ragents.utils.logger import logger


class LocalProvider(LLMProvider):
    """Local LLM provider via Ollama or vLLM OpenAI-compatible endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._name = "local"

    @property
    def name(self) -> str:
        return self._name

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Chat via Ollama /api/chat endpoint."""
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        logger.info(
            "local_chat",
            model=self.model,
            url=url,
            messages_count=len(messages),
        )

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            logger.info(
                "local_chat_done",
                model=self.model,
                response_length=len(content),
            )
            return content

        except requests.Timeout as e:
            raise LLMTimeoutError(
                f"Local LLM timeout: {e}",
                context={"provider": self.name, "model": self.model, "url": url},
            ) from e
        except Exception as e:
            raise LLMError(
                f"Local LLM chat failed: {e}",
                context={"provider": self.name, "model": self.model, "url": url},
            ) from e

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed via Ollama /api/embed endpoint."""
        url = f"{self.base_url}/api/embed"

        logger.info(
            "local_embed",
            model=self.model,
            batch_size=len(texts),
        )

        try:
            response = requests.post(
                url,
                json={"model": self.model, "input": texts},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings", [])
            logger.info(
                "local_embed_done",
                batch_size=len(texts),
            )
            return embeddings

        except requests.Timeout as e:
            raise LLMTimeoutError(
                f"Local embedding timeout: {e}",
                context={"provider": self.name, "model": self.model},
            ) from e
        except Exception as e:
            raise LLMError(
                f"Local embedding failed: {e}",
                context={"provider": self.name, "model": self.model},
            ) from e
