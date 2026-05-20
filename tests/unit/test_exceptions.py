"""Exception hierarchy unit tests.

Covers all exception classes in ragents.errors:
- Instantiation and attribute access
- Inheritance hierarchy
- retryable flags
- Context propagation
- ToolExecutionError special attributes
"""

from __future__ import annotations

import pytest

from ragents.errors import (
    AgentError,
    AgentExecutionError,
    AgentMaxStepsError,
    AgentPlanningError,
    ConfigError,
    ConfigMissingKeyError,
    ConfigParseError,
    EmbeddingError,
    EmbeddingModelError,
    IndexCorruptedError,
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    MCPConnectionError,
    MCPError,
    MCPProtocolError,
    MCPToolNotFoundError,
    MCPTimeoutError,
    QueryParseError,
    RAGentError,
    RetrievalError,
    ToolError,
    ToolExecutionError,
    ToolTimeoutError,
    ToolValidationError,
)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class TestRAGentError:
    def test_basic_instantiation(self):
        err = RAGentError("something went wrong")
        assert err.message == "something went wrong"
        assert err.error_code == "UNKNOWN"
        assert err.retryable is False
        assert err.context == {}
        assert str(err) == "something went wrong"

    def test_with_context(self):
        err = RAGentError("fail", context={"key": "value", "num": 42})
        assert err.context == {"key": "value", "num": 42}

    def test_is_exception_subclass(self):
        assert issubclass(RAGentError, Exception)


# ---------------------------------------------------------------------------
# LLM Error Family
# ---------------------------------------------------------------------------


class TestLLMErrorFamily:
    def test_llm_error_base(self):
        err = LLMError("generic llm error")
        assert err.error_code == "LLM_ERROR"
        assert err.retryable is False
        assert isinstance(err, RAGentError)

    def test_rate_limit(self):
        err = LLMRateLimitError("rate limit hit")
        assert err.error_code == "LLM_RATE_LIMIT"
        assert err.retryable is True
        assert isinstance(err, LLMError)

    def test_timeout(self):
        err = LLMTimeoutError("socket timeout")
        assert err.error_code == "LLM_TIMEOUT"
        assert err.retryable is True
        assert isinstance(err, LLMError)

    def test_auth(self):
        err = LLMAuthenticationError("invalid key")
        assert err.error_code == "LLM_AUTH"
        assert err.retryable is False
        assert isinstance(err, LLMError)

    def test_content_filter(self):
        err = LLMContentFilterError("content blocked")
        assert err.error_code == "LLM_CONTENT_FILTER"
        assert err.retryable is False
        assert isinstance(err, LLMError)

    def test_all_llm_are_ragent(self):
        for cls in [LLMError, LLMRateLimitError, LLMTimeoutError,
                    LLMAuthenticationError, LLMContentFilterError]:
            assert issubclass(cls, RAGentError)


# ---------------------------------------------------------------------------
# Retrieval Error Family
# ---------------------------------------------------------------------------


class TestRetrievalErrorFamily:
    def test_base(self):
        err = RetrievalError("index issue")
        assert err.error_code == "RETRIEVAL_ERROR"
        assert err.retryable is False

    def test_index_corrupted(self):
        err = IndexCorruptedError("checksum mismatch")
        assert err.error_code == "RETRIEVAL_INDEX_CORRUPTED"
        assert isinstance(err, RetrievalError)

    def test_query_parse(self):
        err = QueryParseError("bad syntax")
        assert err.error_code == "RETRIEVAL_QUERY_PARSE"
        assert isinstance(err, RetrievalError)


# ---------------------------------------------------------------------------
# Tool Error Family
# ---------------------------------------------------------------------------


class TestToolErrorFamily:
    def test_base(self):
        err = ToolError("tool issue")
        assert err.error_code == "TOOL_ERROR"
        assert err.retryable is False

    def test_execution(self):
        err = ToolExecutionError("runtime failure")
        assert err.error_code == "TOOL_EXECUTION"
        assert err.tool_name == ""
        assert err.original_error is None
        assert isinstance(err, ToolError)

    def test_execution_with_tool_name_and_original(self):
        original = ValueError("original")
        err = ToolExecutionError(
            "failed",
            tool_name="query",
            original_error=original,
            context={"arg": "x"},
        )
        assert err.tool_name == "query"
        assert err.original_error is original
        assert err.context == {"arg": "x"}

    def test_timeout(self):
        err = ToolTimeoutError("tool took too long")
        assert err.error_code == "TOOL_TIMEOUT"
        assert err.retryable is True
        assert isinstance(err, ToolExecutionError)
        assert isinstance(err, ToolError)

    def test_validation(self):
        err = ToolValidationError("bad args")
        assert err.error_code == "TOOL_VALIDATION"
        assert err.retryable is False
        assert isinstance(err, ToolError)


# ---------------------------------------------------------------------------
# MCP Error Family
# ---------------------------------------------------------------------------


class TestMCPErrorFamily:
    def test_base(self):
        err = MCPError("mcp issue")
        assert err.error_code == "MCP_ERROR"
        assert err.retryable is False

    def test_connection(self):
        err = MCPConnectionError("stdio broken")
        assert err.error_code == "MCP_CONNECTION"
        assert err.retryable is True
        assert isinstance(err, MCPError)

    def test_timeout(self):
        err = MCPTimeoutError("server timeout")
        assert err.error_code == "MCP_TIMEOUT"
        assert err.retryable is True
        assert isinstance(err, MCPError)

    def test_tool_not_found(self):
        err = MCPToolNotFoundError("unknown tool")
        assert err.error_code == "MCP_TOOL_NOT_FOUND"
        assert err.retryable is False
        assert isinstance(err, MCPError)

    def test_protocol(self):
        err = MCPProtocolError("version mismatch")
        assert err.error_code == "MCP_PROTOCOL"
        assert err.retryable is False
        assert isinstance(err, MCPError)


# ---------------------------------------------------------------------------
# Agent Error Family
# ---------------------------------------------------------------------------


class TestAgentErrorFamily:
    def test_base(self):
        err = AgentError("agent issue")
        assert err.error_code == "AGENT_ERROR"
        assert err.retryable is False

    def test_planning(self):
        err = AgentPlanningError("plan invalid")
        assert err.error_code == "AGENT_PLANNING"
        assert err.retryable is True
        assert isinstance(err, AgentError)

    def test_execution(self):
        err = AgentExecutionError("critical failure")
        assert err.error_code == "AGENT_EXECUTION"
        assert err.retryable is False
        assert isinstance(err, AgentError)

    def test_max_steps(self):
        err = AgentMaxStepsError("too many steps")
        assert err.error_code == "AGENT_MAX_STEPS"
        assert err.retryable is False
        assert isinstance(err, AgentError)


# ---------------------------------------------------------------------------
# Embedding Error Family
# ---------------------------------------------------------------------------


class TestEmbeddingErrorFamily:
    def test_base(self):
        err = EmbeddingError("embed issue")
        assert err.error_code == "EMBED_ERROR"
        assert err.retryable is False

    def test_model_error(self):
        err = EmbeddingModelError("model corrupt")
        assert err.error_code == "EMBED_MODEL_ERROR"
        assert isinstance(err, EmbeddingError)


# ---------------------------------------------------------------------------
# Config Error Family
# ---------------------------------------------------------------------------


class TestConfigErrorFamily:
    def test_base(self):
        err = ConfigError("config issue")
        assert err.error_code == "CONFIG_ERROR"
        assert err.retryable is False

    def test_missing_key(self):
        err = ConfigMissingKeyError("missing API_KEY")
        assert err.error_code == "CONFIG_MISSING_KEY"
        assert isinstance(err, ConfigError)

    def test_parse_error(self):
        err = ConfigParseError("invalid toml")
        assert err.error_code == "CONFIG_PARSE_ERROR"
        assert isinstance(err, ConfigError)


# ---------------------------------------------------------------------------
# Hierarchy verification
# ---------------------------------------------------------------------------


class TestHierarchy:
    """Verify the full inheritance tree matches docs/zh/error_handling.md."""

    def test_all_subclasses_of_ragent(self):
        all_exceptions = [
            LLMError, LLMRateLimitError, LLMTimeoutError, LLMAuthenticationError, LLMContentFilterError,
            RetrievalError, IndexCorruptedError, QueryParseError,
            ToolError, ToolExecutionError, ToolTimeoutError, ToolValidationError,
            MCPError, MCPConnectionError, MCPTimeoutError, MCPToolNotFoundError, MCPProtocolError,
            AgentError, AgentPlanningError, AgentExecutionError, AgentMaxStepsError,
            EmbeddingError, EmbeddingModelError,
            ConfigError, ConfigMissingKeyError, ConfigParseError,
        ]
        for cls in all_exceptions:
            assert issubclass(cls, RAGentError), f"{cls.__name__} is not a RAGentError"

    def test_tool_timeout_is_tool_execution(self):
        assert issubclass(ToolTimeoutError, ToolExecutionError)

    def test_tool_timeout_is_tool_error(self):
        assert issubclass(ToolTimeoutError, ToolError)


# ---------------------------------------------------------------------------
# Retryable flag matrix
# ---------------------------------------------------------------------------


class TestRetryableFlags:
    """Verify retryable flags match the decision matrix in error_handling.md."""

    RETRYABLE = [
        LLMRateLimitError,
        LLMTimeoutError,
        ToolTimeoutError,
        MCPConnectionError,
        MCPTimeoutError,
        AgentPlanningError,
    ]

    NOT_RETRYABLE = [
        RAGentError,
        LLMError,
        LLMAuthenticationError,
        LLMContentFilterError,
        RetrievalError,
        IndexCorruptedError,
        QueryParseError,
        ToolError,
        ToolExecutionError,
        ToolValidationError,
        MCPError,
        MCPToolNotFoundError,
        MCPProtocolError,
        AgentError,
        AgentExecutionError,
        AgentMaxStepsError,
        EmbeddingError,
        EmbeddingModelError,
        ConfigError,
        ConfigMissingKeyError,
        ConfigParseError,
    ]

    def test_retryable(self):
        for cls in self.RETRYABLE:
            err = cls("test")
            assert err.retryable is True, f"{cls.__name__} should be retryable"

    def test_not_retryable(self):
        for cls in self.NOT_RETRYABLE:
            err = cls("test")
            assert err.retryable is False, f"{cls.__name__} should not be retryable"


# ---------------------------------------------------------------------------
# Error code format
# ---------------------------------------------------------------------------


class TestErrorCodes:
    def test_all_codes_are_uppercase_with_underscores(self):
        all_exceptions = [
            RAGentError,
            LLMError, LLMRateLimitError, LLMTimeoutError, LLMAuthenticationError, LLMContentFilterError,
            RetrievalError, IndexCorruptedError, QueryParseError,
            ToolError, ToolExecutionError, ToolTimeoutError, ToolValidationError,
            MCPError, MCPConnectionError, MCPTimeoutError, MCPToolNotFoundError, MCPProtocolError,
            AgentError, AgentPlanningError, AgentExecutionError, AgentMaxStepsError,
            EmbeddingError, EmbeddingModelError,
            ConfigError, ConfigMissingKeyError, ConfigParseError,
        ]
        for cls in all_exceptions:
            err = cls("test")
            code = err.error_code
            assert code == code.upper(), f"{cls.__name__}.error_code not uppercase: {code}"
            assert "_" in code or code == "UNKNOWN", f"{cls.__name__}.error_code missing underscore: {code}"

    def test_error_code_prefixes(self):
        """Verify error codes follow {LAYER}_{CAUSE} format."""
        checks = [
            (LLMError, "LLM_"),
            (RetrievalError, "RETRIEVAL_"),
            (ToolError, "TOOL_"),
            (MCPError, "MCP_"),
            (AgentError, "AGENT_"),
            (EmbeddingError, "EMBED_"),
            (ConfigError, "CONFIG_"),
        ]
        for cls, prefix in checks:
            err = cls("test")
            assert err.error_code.startswith(prefix) or err.error_code == "UNKNOWN"
