"""Unit tests for graph_index module."""

from ragents.rag.graph_index import GraphIndex
from ragents.schema.chunk import Chunk, ChunkMeta


class TestGraphIndex:
    """Tests for GraphIndex (currently a stub)."""

    def test_init(self):
        """GraphIndex can be instantiated."""
        idx = GraphIndex()
        assert idx is not None

    def test_add_noop(self):
        """add() accepts chunks without error."""
        idx = GraphIndex()
        chunk = Chunk(
            id="doc#1",
            text="hello world",
            meta=ChunkMeta(source="test.txt"),
        )
        idx.add(chunk)  # Should not raise

    def test_search_returns_empty(self):
        """search() returns empty list."""
        idx = GraphIndex()
        results = idx.search("hello")
        assert results == []

    def test_search_with_top_k(self):
        """search() ignores top_k and returns empty list."""
        idx = GraphIndex()
        results = idx.search("hello", top_k=10)
        assert results == []

    def test_add_then_search(self):
        """Adding chunks doesn't affect search results (stub)."""
        idx = GraphIndex()
        for i in range(3):
            idx.add(Chunk(
                id=f"doc#{i}",
                text=f"chunk {i}",
                meta=ChunkMeta(source="test.txt"),
            ))
        results = idx.search("chunk")
        assert results == []
