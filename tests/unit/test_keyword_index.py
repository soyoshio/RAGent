"""Unit tests for keyword_index module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ragents.rag.keyword_index import KeywordIndex
from ragents.schema.chunk import Chunk, ChunkMeta


def _make_bm25_mock():
    """Create a mock BM25Okapi class that returns a mock instance."""
    mock_instance = MagicMock()

    def mock_constructor(tokenized_corpus):
        mock_instance._tokenized_corpus = tokenized_corpus
        return mock_instance

    return mock_constructor, mock_instance


def _with_bm25_mock(test_func):
    """Decorator-like helper to run test with BM25Okapi mocked via __import__."""
    mock_constructor, mock_instance = _make_bm25_mock()

    def fake_import(name, *args, **kwargs):
        if name == "rank_bm25":
            mod = MagicMock()
            mod.BM25Okapi = mock_constructor
            return mod
        return __builtins__["__import__"](name, *args, **kwargs)

    with patch("builtins.__import__") as mock_import:
        mock_import.side_effect = fake_import
        return test_func(mock_instance)


class TestKeywordIndexInit:
    """Tests for KeywordIndex initialization."""

    def test_init_empty(self):
        """Fresh index has empty state."""
        idx = KeywordIndex()
        assert idx._chunks == {}
        assert idx._corpus == []
        assert idx._chunk_ids == []
        assert idx._bm25 is None


class TestKeywordIndexAdd:
    """Tests for adding chunks."""

    def test_add_single(self):
        """Add a single chunk."""
        idx = KeywordIndex()
        chunk = Chunk(
            id="doc#1",
            text="hello world",
            meta=ChunkMeta(source="test.txt"),
        )
        idx.add([chunk])

        assert len(idx._chunks) == 1
        assert idx._chunks["doc#1"] == chunk
        assert idx._chunk_ids == ["doc#1"]
        assert idx._corpus == ["hello world"]
        assert idx._bm25 is None  # Reset after add

    def test_add_multiple(self):
        """Add multiple chunks."""
        idx = KeywordIndex()
        chunks = [
            Chunk(id="doc#1", text="first chunk", meta=ChunkMeta(source="a.txt")),
            Chunk(id="doc#2", text="second chunk", meta=ChunkMeta(source="b.txt")),
        ]
        idx.add(chunks)

        assert len(idx._chunks) == 2
        assert idx._chunk_ids == ["doc#1", "doc#2"]
        assert idx._corpus == ["first chunk", "second chunk"]

    def test_add_appends(self):
        """Adding to existing index appends."""
        idx = KeywordIndex()
        idx.add([Chunk(id="doc#1", text="first", meta=ChunkMeta(source="a.txt"))])
        idx.add([Chunk(id="doc#2", text="second", meta=ChunkMeta(source="b.txt"))])

        assert len(idx._chunks) == 2
        assert idx._chunk_ids == ["doc#1", "doc#2"]

    def test_add_resets_bm25(self):
        """Adding chunks resets cached BM25."""
        idx = KeywordIndex()
        idx.add([Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt"))])

        # Simulate BM25 being built
        idx._bm25 = MagicMock()
        idx.add([Chunk(id="doc#2", text="world", meta=ChunkMeta(source="b.txt"))])

        assert idx._bm25 is None


class TestKeywordIndexSearch:
    """Tests for search functionality."""

    def test_search_empty_corpus(self):
        """Search on empty index returns empty list."""
        idx = KeywordIndex()
        results = idx.search("hello")
        assert results == []

    def test_search_missing_bm25_package(self):
        """Missing rank-bm25 raises ImportError."""
        idx = KeywordIndex()
        idx.add([Chunk(id="doc#1", text="hello world", meta=ChunkMeta(source="a.txt"))])

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "rank_bm25":
                    raise ImportError("No module named 'rank_bm25'")
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            with pytest.raises(ImportError) as exc:
                idx.search("hello")
            assert "rank-bm25 not installed" in str(exc.value)

    def test_search_success(self):
        """Successful search returns scored results."""
        idx = KeywordIndex()
        idx.add([
            Chunk(id="doc#1", text="hello world", meta=ChunkMeta(source="a.txt")),
            Chunk(id="doc#2", text="foo bar", meta=ChunkMeta(source="b.txt")),
        ])

        def run_test(mock_bm25):
            mock_bm25.get_scores.return_value = [1.5, 0.5]
            results = idx.search("hello", top_k=2)

            assert len(results) == 2
            assert results[0].chunk.id == "doc#1"
            assert results[0].score == 1.5
            assert results[1].chunk.id == "doc#2"
            assert results[1].score == 0.5
            return results

        _with_bm25_mock(run_test)

    def test_search_top_k_limits(self):
        """top_k limits number of results."""
        idx = KeywordIndex()
        idx.add([
            Chunk(id="doc#1", text="hello world", meta=ChunkMeta(source="a.txt")),
            Chunk(id="doc#2", text="hello there", meta=ChunkMeta(source="b.txt")),
            Chunk(id="doc#3", text="foo bar", meta=ChunkMeta(source="c.txt")),
        ])

        def run_test(mock_bm25):
            mock_bm25.get_scores.return_value = [2.0, 1.5, 0.5]
            results = idx.search("hello", top_k=2)

            assert len(results) == 2
            assert results[0].chunk.id == "doc#1"
            assert results[1].chunk.id == "doc#2"
            return results

        _with_bm25_mock(run_test)

    def test_search_default_top_k(self):
        """Default top_k is 5."""
        idx = KeywordIndex()
        for i in range(10):
            idx.add([Chunk(
                id=f"doc#{i}",
                text=f"chunk {i}",
                meta=ChunkMeta(source="a.txt"),
            )])

        def run_test(mock_bm25):
            mock_bm25.get_scores.return_value = list(range(10))
            results = idx.search("test")

            assert len(results) == 5  # default top_k
            return results

        _with_bm25_mock(run_test)

    def test_search_tokenizes_query(self):
        """Query is lowercased and tokenized."""
        idx = KeywordIndex()
        idx.add([Chunk(id="doc#1", text="Hello World", meta=ChunkMeta(source="a.txt"))])

        def run_test(mock_bm25):
            mock_bm25.get_scores.return_value = [1.0]
            idx.search("Hello World")

            mock_bm25.get_scores.assert_called_once_with(["hello", "world"])

        _with_bm25_mock(run_test)

    def test_search_corpus_tokenized(self):
        """Corpus is lowercased and tokenized for BM25."""
        idx = KeywordIndex()
        idx.add([Chunk(id="doc#1", text="Hello World", meta=ChunkMeta(source="a.txt"))])

        captured_corpus = []

        def run_test(mock_bm25):
            mock_bm25.get_scores.return_value = [1.0]
            idx.search("test")
            # The mock constructor captured the tokenized corpus
            return mock_bm25

        mock_constructor, mock_instance = _make_bm25_mock()

        def tracking_constructor(tokenized_corpus):
            captured_corpus.extend(tokenized_corpus)
            mock_instance._tokenized_corpus = tokenized_corpus
            return mock_instance

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "rank_bm25":
                    mod = MagicMock()
                    mod.BM25Okapi = tracking_constructor
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import
            mock_instance.get_scores.return_value = [1.0]
            idx.search("test")

        assert captured_corpus == [["hello", "world"]]

    def test_search_bm25_cached(self):
        """BM25 is built once and cached."""
        idx = KeywordIndex()
        idx.add([Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt"))])

        call_count = 0

        def run_test(mock_bm25):
            nonlocal call_count
            mock_bm25.get_scores.return_value = [1.0]
            idx.search("hello")
            idx.search("world")
            call_count = mock_bm25.get_scores.call_count
            return mock_bm25

        _with_bm25_mock(run_test)
        assert call_count == 2


class TestKeywordIndexPersistence:
    """Tests for save/load."""

    def test_save_creates_directory(self, tmp_path):
        """Save creates parent directories."""
        idx = KeywordIndex()
        idx.add([Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt"))])

        save_path = tmp_path / "nested" / "index"
        idx.save(save_path)

        assert save_path.exists()
        assert (save_path / "keyword_index.json").exists()

    def test_save_content(self, tmp_path):
        """Save writes correct JSON structure."""
        idx = KeywordIndex()
        chunk = Chunk(id="doc#1", text="hello world", meta=ChunkMeta(source="a.txt"))
        idx.add([chunk])

        save_path = tmp_path / "index"
        idx.save(save_path)

        with open(save_path / "keyword_index.json") as f:
            data = json.load(f)

        assert data["chunk_ids"] == ["doc#1"]
        assert data["corpus"] == ["hello world"]
        assert "doc#1" in data["chunks"]
        assert data["chunks"]["doc#1"]["text"] == "hello world"

    def test_load_success(self, tmp_path):
        """Load restores index from disk."""
        idx = KeywordIndex()
        chunk = Chunk(id="doc#1", text="hello world", meta=ChunkMeta(source="a.txt"))
        idx.add([chunk])

        save_path = tmp_path / "index"
        idx.save(save_path)

        # Load into fresh index
        idx2 = KeywordIndex()
        idx2.load(save_path)

        assert len(idx2._chunks) == 1
        assert idx2._chunks["doc#1"].text == "hello world"
        assert idx2._chunk_ids == ["doc#1"]
        assert idx2._corpus == ["hello world"]
        assert idx2._bm25 is None  # Rebuilt on next search

    def test_load_file_not_found(self, tmp_path):
        """Load missing file raises FileNotFoundError."""
        idx = KeywordIndex()
        with pytest.raises(FileNotFoundError) as exc:
            idx.load(tmp_path / "nonexistent")
        assert "Keyword index not found" in str(exc.value)

    def test_roundtrip(self, tmp_path):
        """Save and load roundtrip preserves data."""
        idx = KeywordIndex()
        chunks = [
            Chunk(id="doc#1", text="first", meta=ChunkMeta(source="a.txt")),
            Chunk(id="doc#2", text="second", meta=ChunkMeta(source="b.txt")),
        ]
        idx.add(chunks)

        save_path = tmp_path / "index"
        idx.save(save_path)

        idx2 = KeywordIndex()
        idx2.load(save_path)

        assert idx2._chunk_ids == ["doc#1", "doc#2"]
        assert idx2._corpus == ["first", "second"]
        assert idx2._chunks["doc#1"].meta.source == "a.txt"
        assert idx2._chunks["doc#2"].meta.source == "b.txt"

    def test_load_rebuilds_bm25_on_search(self, tmp_path):
        """Loaded index rebuilds BM25 on first search."""
        idx = KeywordIndex()
        idx.add([Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt"))])

        save_path = tmp_path / "index"
        idx.save(save_path)

        idx2 = KeywordIndex()
        idx2.load(save_path)
        assert idx2._bm25 is None

        def run_test(mock_bm25):
            mock_bm25.get_scores.return_value = [1.0]
            results = idx2.search("hello")

            assert len(results) == 1
            assert idx2._bm25 is mock_bm25
            return results

        _with_bm25_mock(run_test)
