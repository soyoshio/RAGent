"""Graceful fallback strategies (local Tool fallback)."""


class Fallback:
    """Falls back to local tools when MCP is unavailable."""

    def fallback(self, tool_name: str, args: dict):
        raise NotImplementedError("No fallback available for {tool_name}")
