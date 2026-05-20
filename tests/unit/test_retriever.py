"""Retriever unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ragents.rag.retriever import (
    BaseRetriever,
    FusionRetriever,
    KeywordRetriever,
    VectorRetriever,
)
from ragents.schema.chunk import Chunk, ChunkMeta
from ragents.schema.retrieval import RetrievedChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def chunk_a():
    return Chunk(
        id="chunk_a#1",
        text="React useState hook documentation",
        meta=ChunkMeta(source="react.md", start_line=1, end_line=5),
    )


@pytest.fixture
def chunk_b():
    return Chunk(
        id="chunk_b#1",
        text="React useEffect hook for side effects",
        meta=ChunkMeta(source="react.md", start_line=6, end_line=10),
    )


@pytest.fixture
def chunk_c():
    return Chunk(
        id="chunk_c#1",
        text="Vue composition API reactive state",
        meta=ChunkMeta(source="vue.md", start_line=1, end_line=5),
    )


@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1, 0.2, 0.3]
    return embedder


@pytest.fixture
def mock_vector_index():
    index = MagicMock()
    index.search.return_value = []
    return index


@pytest.fixture
def mock_keyword_index():
    index = MagicMock()
    index.search.return_value = []
    return index


# ---------------------------------------------------------------------------
# BaseRetriever
# ---------------------------------------------------------------------------


class TestBaseRetriever:
    """Tests for the abstract BaseRetriever."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseRetriever()

    def test_batch_retrieve_delegates_to_retrieve(self, chunk_a, chunk_b):
        """batch_retrieve should call retrieve() for each query."""

        class DummyRetriever(BaseRetriever):
            def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
                return [RetrievedChunk(chunk=chunk_a if "a" in query else chunk_b, score=1.0)]

        retriever = DummyRetriever()
        results = retriever.batch_retrieve(["query a", "query b"], top_k=3)

        assert len(results) == 2
        assert results[0][0].chunk.id == "chunk_a#1"
        assert results[1][0].chunk.id == "chunk_b#1"

    def test_batch_retrieve_empty_queries(self):
        class DummyRetriever(BaseRetriever):
            def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
                return []

        retriever = DummyRetriever()
        results = retriever.batch_retrieve([])
        assert results == []

    def test_batch_retrieve_default_top_k(self, chunk_a):
        class DummyRetriever(BaseRetriever):
            def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
                return [RetrievedChunk(chunk=chunk_a, score=1.0)]

        retriever = DummyRetriever()
        results = retriever.batch_retrieve(["q1"])
        assert len(results) == 1


# ---------------------------------------------------------------------------
# VectorRetriever
# ---------------------------------------------------------------------------


class TestVectorRetriever:
    """Tests for VectorRetriever."""

    def test_retrieve_calls_embedder_and_index(self, mock_embedder, mock_vector_index, chunk_a):
        mock_vector_index.search.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.95),
        ]

        retriever = VectorRetriever(mock_vector_index, mock_embedder)
        results = retriever.retrieve("react hooks", top_k=3)

        mock_embedder.embed_query.assert_called_once_with("react hooks")
        mock_vector_index.search.assert_called_once_with([0.1, 0.2, 0.3], top_k=3)
        assert len(results) == 1
        assert results[0].chunk.id == "chunk_a#1"
        assert results[0].score == 0.95

    def test_retrieve_empty_results(self, mock_embedder, mock_vector_index):
        retriever = VectorRetriever(mock_vector_index, mock_embedder)
        results = retriever.retrieve("nonexistent")

        assert results == []

    def test_retrieve_multiple_results(self, mock_embedder, mock_vector_index, chunk_a, chunk_b):
        mock_vector_index.search.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.95),
            RetrievedChunk(chunk=chunk_b, score=0.85),
        ]

        retriever = VectorRetriever(mock_vector_index, mock_embedder)
        results = retriever.retrieve("react", top_k=5)

        assert len(results) == 2
        assert results[0].chunk.id == "chunk_a#1"
        assert results[1].chunk.id == "chunk_b#1"

    def test_retrieve_default_top_k(self, mock_embedder, mock_vector_index):
        retriever = VectorRetriever(mock_vector_index, mock_embedder)
        retriever.retrieve("query")

        mock_vector_index.search.assert_called_once_with([0.1, 0.2, 0.3], top_k=5)

    def test_batch_retrieve(self, mock_embedder, mock_vector_index, chunk_a, chunk_b):
        mock_vector_index.search.side_effect = [
            [RetrievedChunk(chunk=chunk_a, score=0.9)],
            [RetrievedChunk(chunk=chunk_b, score=0.8)],
        ]

        retriever = VectorRetriever(mock_vector_index, mock_embedder)
        results = retriever.batch_retrieve(["q1", "q2"])

        assert len(results) == 2
        assert results[0][0].chunk.id == "chunk_a#1"
        assert results[1][0].chunk.id == "chunk_b#1"
        assert mock_vector_index.search.call_count == 2


# ---------------------------------------------------------------------------
# KeywordRetriever
# ---------------------------------------------------------------------------


class TestKeywordRetriever:
    """Tests for KeywordRetriever."""

    def test_retrieve_calls_keyword_index(self, mock_keyword_index, chunk_a):
        mock_keyword_index.search.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.92),
        ]

        retriever = KeywordRetriever(mock_keyword_index)
        results = retriever.retrieve("react hooks", top_k=5)

        mock_keyword_index.search.assert_called_once_with("react hooks", top_k=5)
        assert len(results) == 1
        assert results[0].chunk.id == "chunk_a#1"

    def test_retrieve_empty_results(self, mock_keyword_index):
        retriever = KeywordRetriever(mock_keyword_index)
        results = retriever.retrieve("nonexistent")

        assert results == []

    def test_retrieve_default_top_k(self, mock_keyword_index):
        retriever = KeywordRetriever(mock_keyword_index)
        retriever.retrieve("query")

        mock_keyword_index.search.assert_called_once_with("query", top_k=5)


# ---------------------------------------------------------------------------
# FusionRetriever
# ---------------------------------------------------------------------------


class TestFusionRetriever:
    """Tests for FusionRetriever with Reciprocal Rank Fusion."""

    def test_retrieve_with_single_retriever(self, chunk_a):
        """Fusion with one retriever should return its results."""
        mock_retriever = MagicMock(spec=BaseRetriever)
        mock_retriever.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.9),
        ]

        fusion = FusionRetriever({"vector": mock_retriever})
        results = fusion.retrieve("react", top_k=5)

        mock_retriever.retrieve.assert_called_once_with("react", top_k=20)
        assert len(results) == 1
        assert results[0].chunk.id == "chunk_a#1"

    def test_retrieve_with_multiple_retrievers(self, chunk_a, chunk_b, chunk_c):
        """RRF should fuse results from multiple retrievers."""
        vector_mock = MagicMock(spec=BaseRetriever)
        vector_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.95),  # rank 1
            RetrievedChunk(chunk=chunk_b, score=0.85),  # rank 2
        ]

        keyword_mock = MagicMock(spec=BaseRetriever)
        keyword_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_b, score=0.92),  # rank 1
            RetrievedChunk(chunk=chunk_c, score=0.80),  # rank 2
        ]

        fusion = FusionRetriever({"vector": vector_mock, "keyword": keyword_mock}, rrf_k=60)
        results = fusion.retrieve("react", top_k=3)

        # chunk_b appears in both retrievers (rank 2 in vector, rank 1 in keyword)
        # chunk_a appears only in vector (rank 1)
        # chunk_c appears only in keyword (rank 2)
        # RRF scores:
        #   chunk_a: 1/(60+1) = 0.01639
        #   chunk_b: 1/(60+2) + 1/(60+1) = 0.01613 + 0.01639 = 0.03252
        #   chunk_c: 1/(60+2) = 0.01613
        # Order should be: chunk_b, chunk_a, chunk_c

        assert len(results) == 3
        assert results[0].chunk.id == "chunk_b#1"  # highest combined score
        assert results[1].chunk.id == "chunk_a#1"
        assert results[2].chunk.id == "chunk_c#1"

    def test_retrieve_respects_top_k(self, chunk_a, chunk_b, chunk_c):
        """Should return exactly top_k results."""
        vector_mock = MagicMock(spec=BaseRetriever)
        vector_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.9),
            RetrievedChunk(chunk=chunk_b, score=0.8),
            RetrievedChunk(chunk=chunk_c, score=0.7),
        ]

        fusion = FusionRetriever({"vector": vector_mock})
        results = fusion.retrieve("react", top_k=2)

        assert len(results) == 2

    def test_retrieve_with_empty_retrievers(self):
        """Fusion with no retrievers should return empty list."""
        fusion = FusionRetriever({})
        results = fusion.retrieve("react", top_k=5)

        assert results == []

    def test_retrieve_with_all_empty_results(self):
        """When all retrievers return empty, fusion returns empty."""
        vector_mock = MagicMock(spec=BaseRetriever)
        vector_mock.retrieve.return_value = []
        keyword_mock = MagicMock(spec=BaseRetriever)
        keyword_mock.retrieve.return_value = []

        fusion = FusionRetriever({"vector": vector_mock, "keyword": keyword_mock})
        results = fusion.retrieve("react", top_k=5)

        assert results == []

    def test_retrieve_retriever_failure_graceful(self, chunk_a, chunk_b):
        """If one retriever fails, others should still contribute."""
        vector_mock = MagicMock(spec=BaseRetriever)
        vector_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.9),
        ]

        failing_mock = MagicMock(spec=BaseRetriever)
        failing_mock.retrieve.side_effect = RuntimeError("index corrupted")

        fusion = FusionRetriever({"vector": vector_mock, "failing": failing_mock})
        results = fusion.retrieve("react", top_k=5)

        assert len(results) == 1
        assert results[0].chunk.id == "chunk_a#1"

    def test_retrieve_all_retrievers_fail(self):
        """If all retrievers fail, fusion returns empty."""
        failing_mock = MagicMock(spec=BaseRetriever)
        failing_mock.retrieve.side_effect = RuntimeError("index corrupted")

        fusion = FusionRetriever({"failing1": failing_mock, "failing2": failing_mock})
        results = fusion.retrieve("react", top_k=5)

        assert results == []

    def test_rrf_fuse_with_tied_ranks(self, chunk_a, chunk_b):
        """RRF should handle chunks with same rank across retrievers."""
        vector_mock = MagicMock(spec=BaseRetriever)
        vector_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.9),  # rank 1
        ]
        keyword_mock = MagicMock(spec=BaseRetriever)
        keyword_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.9),  # rank 1
        ]

        fusion = FusionRetriever({"vector": vector_mock, "keyword": keyword_mock}, rrf_k=60)
        results = fusion.retrieve("react", top_k=5)

        # chunk_a gets 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.0328
        assert len(results) == 1
        assert results[0].chunk.id == "chunk_a#1"
        assert results[0].score == pytest.approx(2 / 61, rel=1e-4)

    def test_rrf_fuse_custom_k_value(self, chunk_a, chunk_b):
        """Custom rrf_k should affect scoring."""
        vector_mock = MagicMock(spec=BaseRetriever)
        vector_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.9),  # rank 1
        ]

        fusion_k10 = FusionRetriever({"vector": vector_mock}, rrf_k=10)
        results_k10 = fusion_k10.retrieve("react", top_k=5)

        fusion_k60 = FusionRetriever({"vector": vector_mock}, rrf_k=60)
        results_k60 = fusion_k60.retrieve("react", top_k=5)

        # Same chunk, different k → different score
        assert results_k10[0].score == pytest.approx(1 / 11, rel=1e-4)
        assert results_k60[0].score == pytest.approx(1 / 61, rel=1e-4)

    def test_retrieve_passes_top_k_times_four(self, chunk_a):
        """Each retriever should be called with top_k * 4."""
        mock = MagicMock(spec=BaseRetriever)
        mock.retrieve.return_value = [RetrievedChunk(chunk=chunk_a, score=0.9)]

        fusion = FusionRetriever({"vector": mock})
        fusion.retrieve("react", top_k=5)

        mock.retrieve.assert_called_once_with("react", top_k=20)

    def test_batch_retrieve_with_fusion(self, chunk_a, chunk_b):
        """batch_retrieve should work through FusionRetriever."""
        mock = MagicMock(spec=BaseRetriever)
        mock.retrieve.side_effect = [
            [RetrievedChunk(chunk=chunk_a, score=0.9)],
            [RetrievedChunk(chunk=chunk_b, score=0.8)],
        ]

        fusion = FusionRetriever({"vector": mock})
        results = fusion.batch_retrieve(["q1", "q2"], top_k=5)

        assert len(results) == 2
        assert results[0][0].chunk.id == "chunk_a#1"
        assert results[1][0].chunk.id == "chunk_b#1"

    def test_rrf_fuse_preserves_chunk_content(self, chunk_a):
        """Fused results should preserve original chunk data."""
        mock = MagicMock(spec=BaseRetriever)
        mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.9),
        ]

        fusion = FusionRetriever({"vector": mock})
        results = fusion.retrieve("react", top_k=5)

        assert results[0].chunk.text == "React useState hook documentation"
        assert results[0].chunk.meta.source == "react.md"

    def test_rrf_fuse_deduplicates_by_chunk_id(self, chunk_a):
        """Same chunk from different retrievers should be deduplicated."""
        vector_mock = MagicMock(spec=BaseRetriever)
        vector_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.95),
        ]
        keyword_mock = MagicMock(spec=BaseRetriever)
        keyword_mock.retrieve.return_value = [
            RetrievedChunk(chunk=chunk_a, score=0.90),
        ]

        fusion = FusionRetriever({"vector": vector_mock, "keyword": keyword_mock})
        results = fusion.retrieve("react", top_k=5)

        # Should only return one result for chunk_a, with combined score
        assert len(results) == 1
        assert results[0].chunk.id == "chunk_a#1"
