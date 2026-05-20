"""Task planner (Plan generation)."""


class Planner:
    """Generates a plan from a user query."""

    def plan(self, query: str):
        from ragents.schema.agent import Plan
        return Plan(steps=[])
