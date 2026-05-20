"""Multi-way recall fusion retriever."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ragents.schema.retrieval import RetrievedChunk
from ragents.utils.logger import logger


class BaseRetriever(ABC):
    """Base class for all retrievers."""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Execute retrieval and return top-k results."""
        ...

    def batch_retrieve(
        self, queries: list[str], top_k: int = 5
    ) -> list[list[RetrievedChunk]]:
        """Default: loop over retrieve(). Subclasses may override for batch optimization."""
        return [self.retrieve(q, top_k) for q in queries]


class VectorRetriever(BaseRetriever):
    """Dense vector similarity retriever."""

    def __init__(self, vector_index, embedder):
        self.vector_index = vector_index
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        query_vector = self.embedder.embed_query(query)
        return self.vector_index.search(query_vector, top_k=top_k)


class KeywordRetriever(BaseRetriever):
    """BM25 keyword retriever."""

    def __init__(self, keyword_index):
        self.keyword_index = keyword_index

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        return self.keyword_index.search(query, top_k=top_k)


class FusionRetriever(BaseRetriever):
    """Fuses results from multiple retrievers using Reciprocal Rank Fusion (RRF).

    RRF formula: score(d) = sum(1 / (k + rank_r(d)))
    where k = 60 (constant to prevent top-ranked items from dominating)
    """

    def __init__(
        self,
        retrievers: dict[str, BaseRetriever],
        rrf_k: int = 60,
    ):
        self.retrievers = retrievers
        self.rrf_k = rrf_k

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Parallel retrieve from all retrievers and fuse with RRF."""
        all_results: dict[str, list[RetrievedChunk]] = {}

        for name, retriever in self.retrievers.items():
            try:
                results = retriever.retrieve(query, top_k=top_k * 4)
                all_results[name] = results
                logger.info(
                    "retriever_results",
                    retriever=name,
                    result_count=len(results),
                )
            except Exception as e:
                logger.error(
                    "retriever_failed",
                    retriever=name,
                    error=str(e),
                )
                all_results[name] = []

        return self._rrf_fuse(all_results, top_k)

    def _rrf_fuse(
        self,
        all_results: dict[str, list[RetrievedChunk]],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Apply Reciprocal Rank Fusion."""
        chunk_scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievedChunk] = {}

        for retriever_name, results in all_results.items():
            for rank, rc in enumerate(results, start=1):
                chunk_id = rc.chunk.id
                score = 1.0 / (self.rrf_k + rank)

                if chunk_id not in chunk_scores:
                    chunk_scores[chunk_id] = 0.0
                    chunk_map[chunk_id] = rc

                chunk_scores[chunk_id] += score

        # Sort by RRF score descending
        sorted_chunks = sorted(
            chunk_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Build result list with fused scores
        fused: list[RetrievedChunk] = []
        for chunk_id, rrf_score in sorted_chunks[:top_k]:
            original = chunk_map[chunk_id]
            fused.append(
                RetrievedChunk(
                    chunk=original.chunk,
                    score=rrf_score,
                )
            )

        logger.info(
            "rrf_fusion",
            input_retrievers=len(all_results),
            fused_count=len(fused),
            top_k=top_k,
        )

        return fused
