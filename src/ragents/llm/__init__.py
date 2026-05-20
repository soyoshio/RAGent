"""LLM abstraction package."""

from ragents.llm.anthropic_provider import AnthropicProvider
from ragents.llm.base import LLMProvider
from ragents.llm.local_provider import LocalProvider
from ragents.llm.openai_provider import OpenAIProvider

PROVIDER_MAP = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "local": LocalProvider,
    "deepseek": OpenAIProvider,  # DeepSeek uses OpenAI-compatible API
}


def create_provider(name: str, config: dict) -> LLMProvider:
    """Factory: create LLM provider by name."""
    from ragents.errors import ConfigError

    provider_cls = PROVIDER_MAP.get(name)
    if not provider_cls:
        raise ConfigError(f"Unknown provider: {name}")
    return provider_cls(**config)


__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "LocalProvider",
    "create_provider",
    "PROVIDER_MAP",
]
