"""Knowledge graph index (concept-entity-relation graph)."""

from typing import List
from ragents.schema.chunk import Chunk


class GraphIndex:
    """Graph-based index for concept/entity relationships."""

    def add(self, chunk: Chunk):
        pass

    def search(self, query: str, top_k: int = 5) -> List[str]:
        return []
