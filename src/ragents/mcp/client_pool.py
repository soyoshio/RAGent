"""MCP Client connection pool + health check."""

from typing import Dict, Any


class ClientPool:
    """Manages MCP client connections with health checks."""

    def __init__(self):
        self._clients: Dict[str, Any] = {}

    def get(self, name: str):
        return self._clients.get(name)

    def register(self, name: str, client: Any):
        self._clients[name] = client
