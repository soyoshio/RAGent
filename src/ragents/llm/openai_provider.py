"""OpenAI / compatible API provider (supports OpenAI, DeepSeek, etc.)."""

from __future__ import annotations

from typing import Any

from ragents.errors import (
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from ragents.llm.base import LLMProvider
from ragents.llm.retry import retry
from ragents.utils.logger import logger


class OpenAIProvider(LLMProvider):
    """OpenAI API provider with DeepSeek compatibility."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
    ):
        if not api_key:
            raise LLMError(
                "API key is required",
                context={"provider": "openai"},
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = None
        self._name = "openai"

    @property
    def name(self) -> str:
        return self._name

    def _get_client(self):
        """Lazy-initialize OpenAI client."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError as e:
            raise LLMError(
                "openai package not installed. Run: pip install openai"
            ) from e

        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )
        return self._client

    @retry(
        max_attempts=3,
        base_delay=1.0,
        retryable_exceptions=(LLMRateLimitError, LLMTimeoutError),
    )
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Send chat completion request."""
        client = self._get_client()

        logger.info(
            "openai_chat",
            model=self.model,
            messages_count=len(messages),
            temperature=temperature,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            content = response.choices[0].message.content or ""
            logger.info(
                "openai_chat_done",
                model=self.model,
                response_length=len(content),
            )
            return content

        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str:
                raise LLMRateLimitError(
                    f"Rate limit exceeded: {e}",
                    context={"provider": self.name, "model": self.model},
                ) from e
            elif "timeout" in error_str:
                raise LLMTimeoutError(
                    f"Request timeout: {e}",
                    context={"provider": self.name, "model": self.model},
                ) from e
            elif "authentication" in error_str or "401" in error_str or "403" in error_str:
                raise LLMAuthenticationError(
                    f"Authentication failed: {e}",
                    context={"provider": self.name, "model": self.model},
                ) from e
            elif "content filter" in error_str:
                raise LLMContentFilterError(
                    f"Content filtered: {e}",
                    context={"provider": self.name, "model": self.model},
                ) from e
            else:
                raise LLMError(
                    f"Chat failed: {e}",
                    context={"provider": self.name, "model": self.model},
                ) from e

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using OpenAI embedding API."""
        if not texts:
            return []

        client = self._get_client()

        logger.info(
            "openai_embed",
            model=self.model,
            batch_size=len(texts),
        )

        try:
            response = client.embeddings.create(
                model=self.model,
                input=texts,
            )
            vectors = [item.embedding for item in response.data]
            logger.info(
                "openai_embed_done",
                batch_size=len(texts),
            )
            return vectors
        except Exception as e:
            raise LLMError(
                f"Embedding failed: {e}",
                context={"provider": self.name, "model": self.model},
            ) from e
