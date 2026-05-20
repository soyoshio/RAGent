"""Schema definitions package.

All public schema models are re-exported here for convenient imports:
    from ragents.schema import Chunk, ChunkMeta, Document, ...
"""

from ragents.schema.chunk import Chunk, ChunkMeta, Document
from ragents.schema.retrieval import FusionResult, RerankResult, RetrievedChunk
from ragents.schema.agent import AgentResult, Observation, Plan, Step
from ragents.schema.tool import Tool, ToolCall, ToolResult
from ragents.schema.skill import SkillConfig, SkillLevel
from ragents.schema.mcp import MCPHealthStatus, MCPServerConfig, MCPSettings

__all__ = [
    # Chunk layer
    "Chunk",
    "ChunkMeta",
    "Document",
    # Retrieval layer
    "RetrievedChunk",
    "FusionResult",
    "RerankResult",
    # Agent layer
    "Observation",
    "Step",
    "Plan",
    "AgentResult",
    # Tool layer
    "Tool",
    "ToolCall",
    "ToolResult",
    # Skill layer
    "SkillLevel",
    "SkillConfig",
    # MCP layer
    "MCPHealthStatus",
    "MCPServerConfig",
    "MCPSettings",
]
