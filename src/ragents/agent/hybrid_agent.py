"""Hybrid Agent: Plan-and-Execute + ReAct."""


class HybridAgent:
    """Combines high-level planning with ReAct execution."""

    def __init__(self, planner, executor, skill_router):
        self.planner = planner
        self.executor = executor
        self.skill_router = skill_router

    def run(self, query: str):
        plan = self.planner.plan(query)
        for step in plan.steps:
            self.executor.execute(step)
        return {"plan": plan, "result": "(stub)"}
