"""Chunk / Document / ChunkMeta schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Any


class ChunkMeta(BaseModel):
    """Metadata attached to each chunk, recording source and position."""

    source: str
    start_line: int | None = None
    end_line: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("end_line")
    @classmethod
    def end_line_ge_start_line(cls, v: int | None, info) -> int | None:
        if v is not None:
            start = info.data.get("start_line")
            if start is not None and v < start:
                raise ValueError("end_line must be >= start_line")
        return v


class Chunk(BaseModel):
    """Atomic context unit for retrieval and generation."""

    id: str
    text: str
    meta: ChunkMeta

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty after stripping")
        return v

    @field_validator("id")
    @classmethod
    def id_format(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z0-9_\-/\.]+#[0-9]+$", v):
            raise ValueError(
                "id must match pattern: ^[a-zA-Z0-9_\\-\\/\\.]+#[0-9]+$"
            )
        return v


class Document(BaseModel):
    """Collection of chunks derived from a single source file."""

    id: str
    chunks: list[Chunk]

    @field_validator("chunks")
    @classmethod
    def chunks_non_empty(cls, v: list[Chunk]) -> list[Chunk]:
        if not v:
            raise ValueError("chunks must not be empty")
        return v

    @field_validator("id")
    @classmethod
    def id_no_hash_suffix(cls, v: str) -> str:
        if "#" in v:
            raise ValueError("document id must not contain '#'")
        return v
