"""Hierarchical exception system for RAGent.

Follows the design in docs/zh/error_handling.md:
- RAGentError base class with error_code, retryable, context
- Layer-specific families: LLM, Retrieval, Tool, MCP, Agent, Embed, Config
- Each family has subtypes for specific failure modes
"""

from __future__ import annotations


class RAGentError(Exception):
    """Base exception for all RAGent errors.

    Attributes:
        error_code: Machine-readable error code (e.g. "LLM_RATE_LIMIT").
        message: Human-readable description.
        retryable: Whether the operation can be retried.
        context: Additional key-value context for logging.
    """

    error_code: str = "UNKNOWN"
    retryable: bool = False

    def __init__(self, message: str, *, context: dict | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


# ---------------------------------------------------------------------------
# LLM Error Family
# ---------------------------------------------------------------------------


class LLMError(RAGentError):
    """Generic LLM provider error."""

    error_code: str = "LLM_ERROR"
    retryable: bool = False


class LLMRateLimitError(LLMError):
    """Rate limit exceeded (HTTP 429)."""

    error_code: str = "LLM_RATE_LIMIT"
    retryable: bool = True


class LLMTimeoutError(LLMError):
    """Socket or read timeout."""

    error_code: str = "LLM_TIMEOUT"
    retryable: bool = True


class LLMAuthenticationError(LLMError):
    """Invalid or expired API key (HTTP 401/403)."""

    error_code: str = "LLM_AUTH"
    retryable: bool = False


class LLMContentFilterError(LLMError):
    """Content policy violation."""

    error_code: str = "LLM_CONTENT_FILTER"
    retryable: bool = False


# ---------------------------------------------------------------------------
# Retrieval Error Family
# ---------------------------------------------------------------------------


class RetrievalError(RAGentError):
    """Generic retrieval/index error."""

    error_code: str = "RETRIEVAL_ERROR"
    retryable: bool = False


class IndexCorruptedError(RetrievalError):
    """Index checksum mismatch or unreadable index file."""

    error_code: str = "RETRIEVAL_INDEX_CORRUPTED"
    retryable: bool = False


class QueryParseError(RetrievalError):
    """Query syntax error."""

    error_code: str = "RETRIEVAL_QUERY_PARSE"
    retryable: bool = False


# ---------------------------------------------------------------------------
# Tool Error Family
# ---------------------------------------------------------------------------


class ToolError(RAGentError):
    """Generic tool error."""

    error_code: str = "TOOL_ERROR"
    retryable: bool = False


class ToolExecutionError(ToolError):
    """Tool runtime failure."""

    error_code: str = "TOOL_EXECUTION"
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        tool_name: str = "",
        original_error: Exception | None = None,
        context: dict | None = None,
    ):
        super().__init__(message, context=context)
        self.tool_name = tool_name
        self.original_error = original_error


class ToolTimeoutError(ToolExecutionError):
    """Tool execution exceeded declared timeout."""

    error_code: str = "TOOL_TIMEOUT"
    retryable: bool = True


class ToolValidationError(ToolError):
    """Tool arguments failed JSON Schema validation."""

    error_code: str = "TOOL_VALIDATION"
    retryable: bool = False


# ---------------------------------------------------------------------------
# MCP Error Family
# ---------------------------------------------------------------------------


class MCPError(RAGentError):
    """Generic MCP protocol error."""

    error_code: str = "MCP_ERROR"
    retryable: bool = False


class MCPConnectionError(MCPError):
    """stdio/SSE transport failure."""

    error_code: str = "MCP_CONNECTION"
    retryable: bool = True


class MCPTimeoutError(MCPError):
    """Tool call exceeded server timeout."""

    error_code: str = "MCP_TIMEOUT"
    retryable: bool = True


class MCPToolNotFoundError(MCPError):
    """Server responded but tool is unknown."""

    error_code: str = "MCP_TOOL_NOT_FOUND"
    retryable: bool = False


class MCPProtocolError(MCPError):
    """Protocol version mismatch or malformed message."""

    error_code: str = "MCP_PROTOCOL"
    retryable: bool = False


# ---------------------------------------------------------------------------
# Agent Error Family
# ---------------------------------------------------------------------------


class AgentError(RAGentError):
    """Generic Agent error."""

    error_code: str = "AGENT_ERROR"
    retryable: bool = False


class AgentPlanningError(AgentError):
    """Planner failed to generate valid plan after retries."""

    error_code: str = "AGENT_PLANNING"
    retryable: bool = True


class AgentExecutionError(AgentError):
    """Critical tool chain failure or unrecoverable executor error."""

    error_code: str = "AGENT_EXECUTION"
    retryable: bool = False


class AgentMaxStepsError(AgentError):
    """Executor reached max_steps limit."""

    error_code: str = "AGENT_MAX_STEPS"
    retryable: bool = False


# ---------------------------------------------------------------------------
# Embedding Error Family
# ---------------------------------------------------------------------------


class EmbeddingError(RAGentError):
    """Generic embedding error."""

    error_code: str = "EMBED_ERROR"
    retryable: bool = False


class EmbeddingModelError(EmbeddingError):
    """Model file corrupted or version incompatible."""

    error_code: str = "EMBED_MODEL_ERROR"
    retryable: bool = False


# ---------------------------------------------------------------------------
# Config Error Family
# ---------------------------------------------------------------------------


class ConfigError(RAGentError):
    """Configuration error."""

    error_code: str = "CONFIG_ERROR"
    retryable: bool = False


class ConfigMissingKeyError(ConfigError):
    """Required configuration key is missing."""

    error_code: str = "CONFIG_MISSING_KEY"
    retryable: bool = False


class ConfigParseError(ConfigError):
    """Configuration file parse error."""

    error_code: str = "CONFIG_PARSE_ERROR"
    retryable: bool = False
