"""MCP schemas."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MCPHealthStatus(str, Enum):
    """MCP server health states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    FAILED = "failed"


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    timeout: float = 30.0
    max_startup_time: float = 10.0
    fallback_tools: list[str] = Field(default_factory=list)


class MCPSettings(BaseModel):
    """Global MCP configuration."""

    enabled: bool = True
    health_check_interval: float = 30.0
    connection_timeout: float = 5.0
    degraded_threshold: int = 2
    down_threshold: int = 5
    auto_restart: bool = False
    servers: list[MCPServerConfig] = Field(default_factory=list)
