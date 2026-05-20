"""Skill schemas."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SkillLevel(str, Enum):
    """Progressive disclosure skill levels."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class SkillConfig(BaseModel):
    """Skill configuration for progressive tool disclosure."""

    name: str
    level: SkillLevel = SkillLevel.BASIC
    enabled: bool = True
    tools: list[str] = Field(default_factory=list)
