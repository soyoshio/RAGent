"""Unit tests for agent module."""

from unittest.mock import MagicMock

import pytest

from ragents.agent.executor import Executor
from ragents.agent.hybrid_agent import HybridAgent
from ragents.agent.planner import Planner
from ragents.agent.skill_router import SkillRouter
from ragents.agent.state import AgentState
from ragents.schema.agent import Observation, Plan, Step


class TestExecutor:
    """Tests for Executor (stub)."""

    def test_init(self):
        """Executor can be instantiated."""
        ex = Executor()
        assert ex is not None

    def test_execute_noop(self):
        """execute() accepts step without error."""
        ex = Executor()
        step = Step(thought="test", action="query")
        ex.execute(step)  # Should not raise

    def test_execute_with_observation(self):
        """execute() accepts step with observation."""
        ex = Executor()
        step = Step(
            thought="test",
            action="query",
            observation=Observation(content="results"),
        )
        ex.execute(step)  # Should not raise


class TestPlanner:
    """Tests for Planner (stub)."""

    def test_init(self):
        """Planner can be instantiated."""
        p = Planner()
        assert p is not None

    def test_plan_returns_plan(self):
        """plan() returns a Plan object."""
        p = Planner()
        result = p.plan("how does X work?")
        assert isinstance(result, Plan)
        assert result.query == "how does X work?"

    def test_plan_empty_steps(self):
        """plan() returns Plan with empty steps."""
        p = Planner()
        result = p.plan("any query")
        assert result.steps == []
        assert result.query == "any query"


class TestSkillRouter:
    """Tests for SkillRouter (stub)."""

    def test_init(self):
        """SkillRouter can be instantiated."""
        sr = SkillRouter()
        assert sr is not None

    def test_route_returns_basic(self):
        """route() returns 'basic'."""
        sr = SkillRouter()
        result = sr.route("any task")
        assert result == "basic"

    def test_route_ignores_input(self):
        """route() ignores input and always returns 'basic'."""
        sr = SkillRouter()
        assert sr.route("") == "basic"
        assert sr.route("complex task") == "basic"
        assert sr.route("simple task") == "basic"


class TestHybridAgent:
    """Tests for HybridAgent."""

    def test_init(self):
        """HybridAgent can be instantiated with dependencies."""
        planner = Planner()
        executor = Executor()
        router = SkillRouter()
        agent = HybridAgent(planner, executor, router)
        assert agent.planner is planner
        assert agent.executor is executor
        assert agent.skill_router is router

    def test_run_returns_result(self):
        """run() returns dict with plan and result."""
        planner = Planner()
        executor = Executor()
        router = SkillRouter()
        agent = HybridAgent(planner, executor, router)

        result = agent.run("how does X work?")

        assert "plan" in result
        assert "result" in result
        assert isinstance(result["plan"], Plan)

    def test_run_with_mock_planner(self):
        """run() uses planner to create plan."""
        mock_planner = MagicMock()
        mock_plan = Plan(query="test", steps=[])
        mock_planner.plan.return_value = mock_plan

        executor = Executor()
        router = SkillRouter()
        agent = HybridAgent(mock_planner, executor, router)

        agent.run("test query")

        mock_planner.plan.assert_called_once_with("test query")

    def test_run_executes_steps(self):
        """run() executes each step in the plan."""
        mock_planner = MagicMock()
        mock_executor = MagicMock()
        mock_plan = Plan(
            query="test",
            steps=[
                Step(thought="step1", action="action1"),
                Step(thought="step2", action="action2"),
            ],
        )
        mock_planner.plan.return_value = mock_plan

        router = SkillRouter()
        agent = HybridAgent(mock_planner, mock_executor, router)
        agent.run("test query")

        assert mock_executor.execute.call_count == 2


class TestAgentState:
    """Tests for AgentState TypedDict."""

    def test_basic_state(self):
        """AgentState can be created with required fields."""
        state: AgentState = {
            "query": "test",
            "plan": None,
            "steps": [],
            "observations": [],
            "result": None,
        }
        assert state["query"] == "test"

    def test_state_with_plan(self):
        """AgentState with a Plan."""
        plan = Plan(query="test", steps=[])
        state: AgentState = {
            "query": "test",
            "plan": plan,
            "steps": [Step(thought="t", action="a")],
            "observations": [Observation(content="o")],
            "result": "answer",
        }
        assert state["plan"] is plan
        assert len(state["steps"]) == 1
        assert len(state["observations"]) == 1
        assert state["result"] == "answer"
