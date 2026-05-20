"""Skill progressive disclosure router."""


class SkillRouter:
    """Routes tasks based on skill level."""

    def route(self, task_description: str):
        return "basic"
