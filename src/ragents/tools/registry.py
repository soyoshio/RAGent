"""ToolRegistry: dynamic registration and discovery."""

from typing import Dict, Callable


class ToolRegistry:
    """Registry for local tools."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        self._tools[name] = func

    def get(self, name: str) -> Callable:
        return self._tools[name]
