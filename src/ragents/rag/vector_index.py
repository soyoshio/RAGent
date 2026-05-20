"""Vector index using numpy-based dense storage."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ragents.schema.chunk import Chunk
from ragents.schema.retrieval import RetrievedChunk
from ragents.utils.logger import logger


class VectorIndex:
    """In-memory vector index with cosine similarity search.

    Uses numpy arrays for storage. For MVP, brute-force search is used.
    Can be upgraded to FAISS/Annoy for larger scale.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._vectors: np.ndarray | None = None
        self._chunk_ids: list[str] = []
        self._chunks: dict[str, Chunk] = {}

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Add chunks with their embedding vectors."""
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) "
                "must have same length"
            )

        new_vectors = np.array(vectors, dtype=np.float32)
        if new_vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Expected dimension {self.dimension}, got {new_vectors.shape[1]}"
            )

        for chunk in chunks:
            self._chunks[chunk.id] = chunk
            self._chunk_ids.append(chunk.id)

        if self._vectors is None:
            self._vectors = new_vectors
        else:
            self._vectors = np.vstack([self._vectors, new_vectors])

        logger.info(
            "vector_index_added",
            chunk_count=len(chunks),
            total_chunks=len(self._chunk_ids),
        )

    def search(self, query_vector: list[float], top_k: int = 5) -> list[RetrievedChunk]:
        """Search for most similar vectors using cosine similarity."""
        if self._vectors is None or len(self._chunk_ids) == 0:
            return []

        query = np.array(query_vector, dtype=np.float32)
        if query.shape[0] != self.dimension:
            raise ValueError(
                f"Query dimension {query.shape[0]} != index dimension {self.dimension}"
            )

        # Normalize vectors for cosine similarity
        query_norm = query / (np.linalg.norm(query) + 1e-10)
        vectors_norm = self._vectors / (
            np.linalg.norm(self._vectors, axis=1, keepdims=True) + 1e-10
        )

        # Compute cosine similarities
        similarities = np.dot(vectors_norm, query_norm)

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results: list[RetrievedChunk] = []
        for idx in top_indices:
            chunk_id = self._chunk_ids[idx]
            chunk = self._chunks[chunk_id]
            score = float(similarities[idx])
            results.append(RetrievedChunk(chunk=chunk, score=score))

        return results

    def save(self, path: Path) -> None:
        """Persist index to disk."""
        path.mkdir(parents=True, exist_ok=True)

        # Save vectors as numpy array
        vectors_file = path / "vectors.npy"
        if self._vectors is not None:
            np.save(vectors_file, self._vectors)

        # Save metadata as JSON
        meta = {
            "dimension": self.dimension,
            "chunk_ids": self._chunk_ids,
            "chunks": {
                cid: chunk.model_dump() for cid, chunk in self._chunks.items()
            },
        }
        meta_file = path / "vector_meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        logger.info(
            "vector_index_saved",
            path=str(path),
            chunk_count=len(self._chunk_ids),
            dimension=self.dimension,
        )

    def load(self, path: Path) -> None:
        """Load index from disk."""
        vectors_file = path / "vectors.npy"
        meta_file = path / "vector_meta.json"

        if not vectors_file.exists() or not meta_file.exists():
            raise FileNotFoundError(f"Vector index not found at {path}")

        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.dimension = meta["dimension"]
        self._chunk_ids = meta["chunk_ids"]
        self._chunks = {
            cid: Chunk(**chunk_data)
            for cid, chunk_data in meta["chunks"].items()
        }
        self._vectors = np.load(vectors_file)

        logger.info(
            "vector_index_loaded",
            path=str(path),
            chunk_count=len(self._chunk_ids),
            dimension=self.dimension,
        )
