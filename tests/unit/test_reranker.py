"""Unit tests for reranker module."""

from ragents.rag.reranker import Reranker
from ragents.schema.chunk import Chunk, ChunkMeta
from ragents.schema.retrieval import RetrievedChunk


class TestReranker:
    """Tests for Reranker (currently a pass-through stub)."""

    def test_init(self):
        """Reranker can be instantiated."""
        r = Reranker()
        assert r is not None

    def test_rerank_empty(self):
        """Rerank empty list returns empty list."""
        r = Reranker()
        results = r.rerank("query", [])
        assert results == []

    def test_rerank_pass_through(self):
        """Rerank returns chunks unchanged (identity)."""
        r = Reranker()
        chunks = [
            RetrievedChunk(
                chunk=Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt")),
                score=0.9,
            ),
            RetrievedChunk(
                chunk=Chunk(id="doc#2", text="world", meta=ChunkMeta(source="b.txt")),
                score=0.8,
            ),
        ]
        results = r.rerank("test query", chunks)

        assert len(results) == 2
        assert results[0].chunk.id == "doc#1"
        assert results[0].score == 0.9
        assert results[1].chunk.id == "doc#2"
        assert results[1].score == 0.8

    def test_rerank_preserves_order(self):
        """Rerank preserves input order."""
        r = Reranker()
        chunks = [
            RetrievedChunk(
                chunk=Chunk(id=f"doc#{i}", text=f"text {i}", meta=ChunkMeta(source="a.txt")),
                score=float(i) / 10,
            )
            for i in range(5)
        ]
        results = r.rerank("query", chunks)

        for i, result in enumerate(results):
            assert result.chunk.id == f"doc#{i}"
            assert result.score == float(i) / 10

    def test_rerank_returns_same_objects(self):
        """Rerank returns the same chunk objects (not copies)."""
        r = Reranker()
        chunk = RetrievedChunk(
            chunk=Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt")),
            score=1.0,
        )
        results = r.rerank("query", [chunk])

        assert results[0] is chunk
