"""LLMProvider abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Send chat completion request."""
        ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        ...

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ):
        """Stream chat completion. Default: raise NotImplementedError."""
        raise NotImplementedError("Streaming not supported by this provider")
