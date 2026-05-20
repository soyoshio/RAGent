"""Configuration system unit tests.

Covers ragents.utils.config:
- Settings default values
- LLMConfig and RAGConfig nested configs
- log_level validation
- create_settings priority chain (toml < env < CLI)
- DeepSeek config fields
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from ragents.schema.mcp import MCPSettings
from ragents.utils.config import LLMConfig, RAGConfig, Settings, _load_toml_config, create_settings


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    def test_openai_defaults(self, monkeypatch):
        # Ensure env vars don't interfere with default tests
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_BASE_URL_OPENAI", raising=False)
        monkeypatch.delenv("DEEPSEEK_BASE_URL_ANTHROPIC", raising=False)
        monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
        monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("VERBOSE", raising=False)
        s = Settings()
        assert s.openai_api_key == ""
        assert s.openai_base_url == "https://api.openai.com/v1"
        assert s.openai_model == "gpt-4o-mini"

    def test_anthropic_defaults(self, monkeypatch):
        # Ensure env vars don't interfere with default tests
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        s = Settings()
        assert s.anthropic_api_key == ""
        assert s.anthropic_base_url == "https://api.anthropic.com"
        assert s.anthropic_model == "claude-3-5-sonnet-20241022"

    def test_deepseek_defaults(self, monkeypatch):
        # Ensure env vars don't interfere with default tests
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_BASE_URL_OPENAI", raising=False)
        monkeypatch.delenv("DEEPSEEK_BASE_URL_ANTHROPIC", raising=False)
        monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
        s = Settings()
        assert s.deepseek_api_key == ""
        assert s.deepseek_base_url_openai == "https://api.deepseek.com"
        assert s.deepseek_base_url_anthropic == "https://api.deepseek.com/anthropic"
        assert s.deepseek_model == "deepseek-v4-flash"

    def test_general_defaults(self, monkeypatch):
        # Ensure env vars don't interfere with default tests
        monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("VERBOSE", raising=False)
        s = Settings()
        assert s.default_llm_provider == "deepseek"
        assert s.log_level == "INFO"
        assert s.verbose is False

    def test_nested_llm_config_defaults(self, monkeypatch):
        # Ensure env vars don't interfere with default tests
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
        monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
        monkeypatch.delenv("LLM_TIMEOUT", raising=False)
        monkeypatch.delenv("LLM_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_EMBEDDING_MODEL", raising=False)
        monkeypatch.delenv("LLM_EMBEDDING_DIMENSION", raising=False)
        s = Settings()
        assert s.llm.provider == "openai"
        assert s.llm.model == "deepseek-v4-flash"
        assert s.llm.temperature == 0.7
        assert s.llm.max_tokens == 4096
        assert s.llm.timeout == 60.0
        assert s.llm.embedding_provider == "local"
        assert s.llm.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert s.llm.embedding_dimension == 384

    def test_nested_rag_config_defaults(self, monkeypatch):
        # Ensure env vars don't interfere with default tests
        monkeypatch.delenv("RAG_TOP_K", raising=False)
        monkeypatch.delenv("RAG_VECTOR_TOP_K", raising=False)
        monkeypatch.delenv("RAG_KEYWORD_TOP_K", raising=False)
        monkeypatch.delenv("RAG_RRF_K", raising=False)
        monkeypatch.delenv("RAG_CHUNK_SIZE", raising=False)
        monkeypatch.delenv("RAG_CHUNK_OVERLAP", raising=False)
        monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
        monkeypatch.delenv("RAG_INDEX_PATH", raising=False)
        s = Settings()
        assert s.rag.top_k == 5
        assert s.rag.vector_top_k == 20
        assert s.rag.keyword_top_k == 20
        assert s.rag.rrf_k == 60
        assert s.rag.chunk_size == 500
        assert s.rag.chunk_overlap == 50
        assert s.rag.reranker_enabled is False
        assert s.rag.index_path == "index"

    def test_nested_mcp_defaults(self):
        s = Settings()
        assert isinstance(s.mcp, MCPSettings)
        assert s.mcp.enabled is True
        assert s.mcp.servers == []


# ---------------------------------------------------------------------------
# log_level validation
# ---------------------------------------------------------------------------


class TestLogLevelValidation:
    def test_valid_levels(self):
        for level in ["debug", "info", "warning", "error", "critical"]:
            s = Settings(log_level=level)
            assert s.log_level == level.upper()

    def test_invalid_level(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(log_level="VERBOSE")
        assert "log_level must be one of" in str(exc_info.value)

    def test_case_insensitive(self):
        s = Settings(log_level="debug")
        assert s.log_level == "DEBUG"


# ---------------------------------------------------------------------------
# Nested config instantiation
# ---------------------------------------------------------------------------


class TestNestedConfigs:
    def test_llm_config_direct(self):
        cfg = LLMConfig(provider="anthropic", model="claude-3", temperature=0.5)
        assert cfg.provider == "anthropic"
        assert cfg.temperature == 0.5

    def test_rag_config_direct(self):
        cfg = RAGConfig(top_k=10, chunk_size=1000)
        assert cfg.top_k == 10
        assert cfg.chunk_size == 1000

    def test_settings_with_custom_nested(self):
        s = Settings(llm=LLMConfig(provider="openai", model="gpt-4"))
        assert s.llm.provider == "openai"
        assert s.llm.model == "gpt-4"


# ---------------------------------------------------------------------------
# _load_toml_config
# ---------------------------------------------------------------------------


class TestLoadTomlConfig:
    def test_missing_file(self, tmp_path: Path):
        result = _load_toml_config(tmp_path / "nonexistent.toml")
        assert result == {}

    def test_valid_toml(self, tmp_path: Path):
        toml_file = tmp_path / "ragents.toml"
        toml_file.write_text('log_level = "DEBUG"\nverbose = true\n')
        result = _load_toml_config(toml_file)
        assert result == {"log_level": "DEBUG", "verbose": True}

    def test_nested_toml(self, tmp_path: Path):
        toml_file = tmp_path / "ragents.toml"
        toml_file.write_text(
            '[llm]\nprovider = "anthropic"\ntemperature = 0.5\n'
        )
        result = _load_toml_config(toml_file)
        assert result == {"llm": {"provider": "anthropic", "temperature": 0.5}}


# ---------------------------------------------------------------------------
# create_settings priority chain
# ---------------------------------------------------------------------------


class TestCreateSettings:
    def test_defaults(self):
        s = create_settings()
        assert s.log_level == "INFO"
        assert s.verbose is False

    def test_cli_override_simple(self):
        s = create_settings(cli_overrides={"log_level": "DEBUG"})
        assert s.log_level == "DEBUG"

    def test_cli_override_deepseek(self):
        s = create_settings(cli_overrides={"deepseek_model": "deepseek-chat"})
        assert s.deepseek_model == "deepseek-chat"

    def test_cli_override_ignores_unknown(self):
        """Unknown keys in cli_overrides are silently ignored via hasattr check."""
        s = create_settings(cli_overrides={"nonexistent_key": "value"})
        assert not hasattr(s, "nonexistent_key")

    def test_toml_override(self, tmp_path: Path, monkeypatch):
        """ragents.toml values are loaded when present."""
        toml_file = tmp_path / "ragents.toml"
        toml_file.write_text('log_level = "DEBUG"\n')
        monkeypatch.chdir(tmp_path)
        s = create_settings()
        assert s.log_level == "DEBUG"

    def test_cli_overrides_toml(self, tmp_path: Path, monkeypatch):
        """CLI overrides have higher priority than toml."""
        toml_file = tmp_path / "ragents.toml"
        toml_file.write_text('log_level = "DEBUG"\n')
        monkeypatch.chdir(tmp_path)
        s = create_settings(cli_overrides={"log_level": "ERROR"})
        assert s.log_level == "ERROR"

    def test_env_var_override(self, monkeypatch):
        """Environment variables override defaults."""
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        s = create_settings()
        assert s.log_level == "WARNING"

    def test_env_overrides_toml(self, tmp_path: Path, monkeypatch):
        """Environment variables have higher priority than toml."""
        toml_file = tmp_path / "ragents.toml"
        toml_file.write_text('log_level = "DEBUG"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("LOG_LEVEL", "ERROR")
        s = create_settings()
        assert s.log_level == "ERROR"

    def test_cli_overrides_env(self, tmp_path: Path, monkeypatch):
        """CLI overrides have highest priority."""
        toml_file = tmp_path / "ragents.toml"
        toml_file.write_text('log_level = "DEBUG"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("LOG_LEVEL", "ERROR")
        s = create_settings(cli_overrides={"log_level": "CRITICAL"})
        assert s.log_level == "CRITICAL"


# ---------------------------------------------------------------------------
# DeepSeek configuration
# ---------------------------------------------------------------------------


class TestDeepSeekConfig:
    def test_all_fields_present(self):
        s = Settings(
            deepseek_api_key="sk-test",
            deepseek_base_url_openai="https://custom.deepseek.com",
            deepseek_base_url_anthropic="https://custom.deepseek.com/anthropic",
            deepseek_model="deepseek-chat",
        )
        assert s.deepseek_api_key == "sk-test"
        assert s.deepseek_base_url_openai == "https://custom.deepseek.com"
        assert s.deepseek_base_url_anthropic == "https://custom.deepseek.com/anthropic"
        assert s.deepseek_model == "deepseek-chat"

    def test_default_provider_is_deepseek(self):
        s = Settings()
        assert s.default_llm_provider == "deepseek"

    def test_llm_config_uses_deepseek_model(self):
        s = Settings()
        assert s.llm.model == "deepseek-v4-flash"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_settings_dump(self):
        s = Settings(log_level="DEBUG", verbose=True)
        data = s.model_dump()
        assert data["log_level"] == "DEBUG"
        assert data["verbose"] is True
        assert "llm" in data
        assert data["llm"]["provider"] == "openai"

    def test_json_mode(self):
        s = Settings()
        data = s.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["log_level"] == "INFO"
