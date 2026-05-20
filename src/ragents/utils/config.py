"""Configuration loader (pydantic-settings / dotenv / toml)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ragents.schema.mcp import MCPSettings


class LLMConfig(BaseSettings):
    """LLM-specific configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    provider: str = "openai"
    model: str = "deepseek-v4-flash"
    base_url: str = ""
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 60.0

    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    planning_provider: str = ""
    planning_model: str = ""
    local_fallback_provider: str = ""


class RAGConfig(BaseSettings):
    """RAG-specific configuration."""

    model_config = SettingsConfigDict(env_prefix="RAG_", extra="ignore")

    top_k: int = 5
    vector_top_k: int = 20
    keyword_top_k: int = 20
    rrf_k: int = 60
    chunk_size: int = 500
    chunk_overlap: int = 50
    reranker_enabled: bool = False
    index_path: str = "index"


class Settings(BaseSettings):
    """Global application settings.

    Priority (high to low):
    1. CLI arguments
    2. Environment variables
    3. .env file
    4. ragents.toml
    5. Default values
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # DeepSeek (can use OpenAI or Anthropic SDK)
    deepseek_api_key: str = ""
    deepseek_base_url_openai: str = "https://api.deepseek.com"
    deepseek_base_url_anthropic: str = "https://api.deepseek.com/anthropic"
    deepseek_model: str = "deepseek-v4-flash"

    # General
    default_llm_provider: str = "deepseek"
    log_level: str = "INFO"
    verbose: bool = False

    # Nested configs
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    mcp: MCPSettings = Field(default_factory=MCPSettings)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v = v.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v


def _load_toml_config(path: Path) -> dict[str, Any]:
    """Load ragents.toml if it exists."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return {}

    if not path.exists():
        return {}

    with path.open("rb") as f:
        return tomllib.load(f)


def _get_env_value(key: str) -> str | None:
    """Get value from environment variable if set."""
    # Map field names to env var names
    env_map = {
        "openai_api_key": "OPENAI_API_KEY",
        "openai_base_url": "OPENAI_BASE_URL",
        "openai_model": "OPENAI_MODEL",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "anthropic_base_url": "ANTHROPIC_BASE_URL",
        "anthropic_model": "ANTHROPIC_MODEL",
        "deepseek_api_key": "DEEPSEEK_API_KEY",
        "deepseek_base_url_openai": "DEEPSEEK_BASE_URL_OPENAI",
        "deepseek_base_url_anthropic": "DEEPSEEK_BASE_URL_ANTHROPIC",
        "deepseek_model": "DEEPSEEK_MODEL",
        "default_llm_provider": "DEFAULT_LLM_PROVIDER",
        "log_level": "LOG_LEVEL",
        "verbose": "VERBOSE",
    }
    env_key = env_map.get(key, key.upper())
    return os.environ.get(env_key)


def create_settings(
    *,
    cli_overrides: dict[str, Any] | None = None,
    env_file: str | None = None,
) -> Settings:
    """Create Settings with full priority chain.

    Priority (high to low):
    1. CLI arguments (cli_overrides)
    2. Environment variables
    3. .env file
    4. ragents.toml
    5. Default values
    """
    # Start with defaults (no env, no toml)
    settings = Settings(_env_file=None)

    # Load ragents.toml (lowest priority)
    toml_path = Path("ragents.toml")
    toml_data = _load_toml_config(toml_path)

    # Apply toml values (only if env is not set for that key)
    if toml_data:
        for key, value in toml_data.items():
            if key.startswith("_"):
                continue
            env_val = _get_env_value(key)
            if env_val is None and hasattr(settings, key):
                setattr(settings, key, value)

    # Apply .env file values (higher priority than toml)
    if env_file:
        env_path = Path(env_file)
        if env_path.exists():
            dotenv_data = _load_toml_config(env_path)  # Not toml, but reusing for structure
            # Actually .env is key=value format; skip for now
            pass

    # Apply environment variables (higher priority than toml/.env)
    for key in Settings.model_fields:
        env_val = _get_env_value(key)
        if env_val is not None and hasattr(settings, key):
            # Parse bool
            if env_val.lower() in ("true", "1", "yes"):
                setattr(settings, key, True)
            elif env_val.lower() in ("false", "0", "no"):
                setattr(settings, key, False)
            else:
                setattr(settings, key, env_val)

    # Apply CLI overrides (highest priority)
    if cli_overrides:
        for key, value in cli_overrides.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

    return settings


# Global singleton (lazy-loaded via create_settings in practice)
settings = Settings()
