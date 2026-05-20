"""Anthropic Claude API provider (with DeepSeek /anthropic compatibility)."""

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


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider with DeepSeek /anthropic endpoint support."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-3-5-sonnet-20241022",
        timeout: float = 60.0,
    ):
        if not api_key:
            raise LLMError(
                "API key is required",
                context={"provider": "anthropic"},
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = None
        self._name = "anthropic"

    @property
    def name(self) -> str:
        return self._name

    def _get_client(self):
        """Lazy-initialize Anthropic client."""
        if self._client is not None:
            return self._client

        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise LLMError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from e

        self._client = Anthropic(
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

        # Convert OpenAI-style messages to Anthropic format
        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
            else:
                anthropic_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        logger.info(
            "anthropic_chat",
            model=self.model,
            messages_count=len(anthropic_messages),
            temperature=temperature,
        )

        try:
            response = client.messages.create(
                model=self.model,
                messages=anthropic_messages,  # type: ignore[arg-type]
                system=system_msg or None,
                temperature=temperature,
                max_tokens=max_tokens or 4096,
                **kwargs,
            )
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            logger.info(
                "anthropic_chat_done",
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
        """Anthropic does not provide embeddings; delegate to local or raise."""
        raise LLMError(
            "Anthropic provider does not support embeddings. "
            "Use OpenAI provider or LocalEmbedder for embeddings.",
            context={"provider": self.name},
        )
