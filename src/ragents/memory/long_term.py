"""Long-term memory interface (vector store / summarization)."""

from typing import List


class LongTermMemory:
    """Interface for long-term memory storage."""

    def save(self, text: str, metadata: dict = None):
        pass

    def search(self, query: str, top_k: int = 5) -> List[str]:
        return []
