"""Keyword inverted index using BM25."""

from __future__ import annotations

import json
from pathlib import Path

from ragents.schema.chunk import Chunk
from ragents.schema.retrieval import RetrievedChunk
from ragents.utils.logger import logger


class KeywordIndex:
    """BM25-based keyword index for sparse retrieval."""

    def __init__(self):
        self._chunks: dict[str, Chunk] = {}
        self._corpus: list[str] = []
        self._chunk_ids: list[str] = []
        self._bm25 = None

    def add(self, chunks: list[Chunk]) -> None:
        """Add chunks to the index."""
        for chunk in chunks:
            self._chunks[chunk.id] = chunk
            self._chunk_ids.append(chunk.id)
            self._corpus.append(chunk.text)

        # Reset BM25 (will be rebuilt on next search)
        self._bm25 = None

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Search for query using BM25 scoring."""
        if not self._corpus:
            return []

        self._ensure_bm25()

        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)

        # Get top-k by score
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results: list[RetrievedChunk] = []
        for idx, score in indexed_scores[:top_k]:
            chunk_id = self._chunk_ids[idx]
            chunk = self._chunks[chunk_id]
            results.append(RetrievedChunk(chunk=chunk, score=float(score)))

        return results

    def _ensure_bm25(self) -> None:
        """Lazy-build BM25 index."""
        if self._bm25 is not None:
            return

        try:
            from rank_bm25 import BM25Okapi
        except ImportError as e:
            raise ImportError(
                "rank-bm25 not installed. Run: pip install rank-bm25"
            ) from e

        logger.info(
            "building_bm25_index",
            corpus_size=len(self._corpus),
        )

        tokenized_corpus = [doc.lower().split() for doc in self._corpus]
        self._bm25 = BM25Okapi(tokenized_corpus)

        logger.info(
            "bm25_index_built",
            corpus_size=len(self._corpus),
        )

    def save(self, path: Path) -> None:
        """Persist index to disk."""
        path.mkdir(parents=True, exist_ok=True)

        data = {
            "chunk_ids": self._chunk_ids,
            "corpus": self._corpus,
            "chunks": {cid: chunk.model_dump() for cid, chunk in self._chunks.items()},
        }

        index_file = path / "keyword_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            "keyword_index_saved",
            path=str(index_file),
            chunk_count=len(self._chunk_ids),
        )

    def load(self, path: Path) -> None:
        """Load index from disk."""
        index_file = path / "keyword_index.json"
        if not index_file.exists():
            raise FileNotFoundError(f"Keyword index not found at {index_file}")

        with open(index_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._chunk_ids = data["chunk_ids"]
        self._corpus = data["corpus"]
        self._chunks = {
            cid: Chunk(**chunk_data)
            for cid, chunk_data in data["chunks"].items()
        }
        self._bm25 = None  # Will be rebuilt on search

        logger.info(
            "keyword_index_loaded",
            path=str(index_file),
            chunk_count=len(self._chunk_ids),
        )
