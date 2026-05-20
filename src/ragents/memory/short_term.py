"""Short-term / multi-turn dialogue cache."""

from typing import List, Dict


class ShortTermMemory:
    """Caches recent conversation turns."""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._history: List[Dict[str, str]] = []

    def add(self, role: str, content: str):
        self._history.append({"role": role, "content": content})
        if len(self._history) > self.max_turns:
            self._history.pop(0)

    def get(self) -> List[Dict[str, str]]:
        return self._history.copy()
