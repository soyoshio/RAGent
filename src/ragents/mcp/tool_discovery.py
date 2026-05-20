"""Dynamic Tool discovery (list_tools)."""

from typing import List
from ragents.schema.tool import Tool


class ToolDiscovery:
    """Discovers tools from an MCP server."""

    def discover(self, client) -> List[Tool]:
        return []
