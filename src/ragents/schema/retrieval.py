"""Retrieval result schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ragents.schema.chunk import Chunk


class RetrievedChunk(BaseModel):
    """Chunk recalled by a retriever with relevance score."""

    chunk: Chunk
    score: float


class FusionResult(BaseModel):
    """Output of multi-way recall fusion."""

    chunks: list[RetrievedChunk]
    sources: dict[str, int] = Field(default_factory=dict)


class RerankResult(BaseModel):
    """Output of reranking stage."""

    chunks: list[RetrievedChunk]
    reranker_name: str = ""
    latency_ms: float = 0.0
