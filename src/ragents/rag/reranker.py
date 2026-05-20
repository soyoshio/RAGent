"""Lightweight reranker (cross-encoder / light model)."""

from typing import List
from ragents.schema.retrieval import RetrievedChunk


class Reranker:
    """Reranks retrieved chunks."""

    def rerank(self, query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        return chunks
