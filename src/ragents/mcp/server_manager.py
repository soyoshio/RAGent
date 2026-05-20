"""MCP Server lifecycle management (start/stop/restart)."""

from typing import Dict, Any


class ServerManager:
    """Manages lifecycle of MCP servers."""

    def __init__(self):
        self._servers: Dict[str, Any] = {}

    def start(self, name: str, config):
        pass

    def stop(self, name: str):
        pass

    def restart(self, name: str):
        self.stop(name)
        self.start(name, self._servers.get(name))
