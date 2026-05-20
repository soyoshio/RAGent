"""Agent state machine (LangGraph-style StateGraph)."""

from typing import TypedDict, List, Any


class AgentState(TypedDict):
    query: str
    plan: Any
    steps: List[Any]
    observations: List[Any]
    result: Any
