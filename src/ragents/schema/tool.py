"""Tool schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class Tool(BaseModel):
    """Tool schema definition for LLM tool selection."""

    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Tool call request from LLM output."""

    tool: str
    arguments: dict


class ToolResult(BaseModel):
    """Result of tool execution."""

    tool: str
    output: Any
    error: str | None = None
    latency_ms: float = 0.0
