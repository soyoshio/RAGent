"""Unit tests for vector_index module."""

import json
from pathlib import Path

import numpy as np
import pytest

from ragents.rag.vector_index import VectorIndex
from ragents.schema.chunk import Chunk, ChunkMeta


class TestVectorIndexInit:
    """Tests for VectorIndex initialization."""

    def test_init_defaults(self):
        """Default dimension is 384."""
        idx = VectorIndex()
        assert idx.dimension == 384
        assert idx._vectors is None
        assert idx._chunk_ids == []
        assert idx._chunks == {}

    def test_init_custom_dimension(self):
        """Custom dimension."""
        idx = VectorIndex(dimension=768)
        assert idx.dimension == 768


class TestVectorIndexAdd:
    """Tests for adding chunks."""

    def test_add_single(self):
        """Add a single chunk with vector."""
        idx = VectorIndex(dimension=3)
        chunk = Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt"))
        idx.add([chunk], [[0.1, 0.2, 0.3]])

        assert len(idx._chunk_ids) == 1
        assert idx._chunk_ids[0] == "doc#1"
        assert idx._chunks["doc#1"] == chunk
        assert idx._vectors is not None
        assert idx._vectors.shape == (1, 3)
        np.testing.assert_array_equal(
            idx._vectors[0], np.array([0.1, 0.2, 0.3], dtype=np.float32)
        )

    def test_add_multiple(self):
        """Add multiple chunks."""
        idx = VectorIndex(dimension=2)
        chunks = [
            Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt")),
            Chunk(id="doc#2", text="b", meta=ChunkMeta(source="b.txt")),
        ]
        idx.add(chunks, [[1.0, 0.0], [0.0, 1.0]])

        assert len(idx._chunk_ids) == 2
        assert idx._vectors.shape == (2, 2)

    def test_add_appends(self):
        """Adding to existing index appends vectors."""
        idx = VectorIndex(dimension=2)
        idx.add(
            [Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt"))],
            [[1.0, 0.0]],
        )
        idx.add(
            [Chunk(id="doc#2", text="b", meta=ChunkMeta(source="b.txt"))],
            [[0.0, 1.0]],
        )

        assert len(idx._chunk_ids) == 2
        assert idx._vectors.shape == (2, 2)
        np.testing.assert_array_equal(idx._vectors[0], [1.0, 0.0])
        np.testing.assert_array_equal(idx._vectors[1], [0.0, 1.0])

    def test_add_mismatched_lengths(self):
        """Mismatched chunks and vectors raises ValueError."""
        idx = VectorIndex(dimension=2)
        chunks = [
            Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt")),
            Chunk(id="doc#2", text="b", meta=ChunkMeta(source="b.txt")),
        ]
        with pytest.raises(ValueError) as exc:
            idx.add(chunks, [[1.0, 0.0]])  # 2 chunks, 1 vector
        assert "must have same length" in str(exc.value)

    def test_add_wrong_dimension(self):
        """Vector dimension mismatch raises ValueError."""
        idx = VectorIndex(dimension=2)
        chunk = Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt"))
        with pytest.raises(ValueError) as exc:
            idx.add([chunk], [[1.0, 0.0, 0.0]])  # 3 dims, expected 2
        assert "Expected dimension 2, got 3" in str(exc.value)

    def test_add_empty(self):
        """Adding empty lists raises IndexError (empty array has no shape[1])."""
        idx = VectorIndex(dimension=2)
        # Empty lists cause IndexError because np.array([]).shape is (0,)
        with pytest.raises(IndexError):
            idx.add([], [])


class TestVectorIndexSearch:
    """Tests for search functionality."""

    def test_search_empty_index(self):
        """Search on empty index returns empty list."""
        idx = VectorIndex(dimension=2)
        results = idx.search([1.0, 0.0])
        assert results == []

    def test_search_basic(self):
        """Basic cosine similarity search."""
        idx = VectorIndex(dimension=2)
        idx.add(
            [Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt"))],
            [[1.0, 0.0]],
        )
        idx.add(
            [Chunk(id="doc#2", text="b", meta=ChunkMeta(source="b.txt"))],
            [[0.0, 1.0]],
        )

        # Query aligned with doc#1
        results = idx.search([1.0, 0.0], top_k=2)

        assert len(results) == 2
        assert results[0].chunk.id == "doc#1"
        assert results[0].score > 0.99  # cosine similarity ~1.0
        assert results[1].chunk.id == "doc#2"

    def test_search_top_k(self):
        """top_k limits results."""
        idx = VectorIndex(dimension=2)
        for i in range(5):
            idx.add(
                [Chunk(id=f"doc#{i}", text=f"t{i}", meta=ChunkMeta(source="a.txt"))],
                [[float(i), 0.0]],
            )

        results = idx.search([1.0, 0.0], top_k=3)
        assert len(results) == 3

    def test_search_wrong_query_dimension(self):
        """Query dimension mismatch raises ValueError."""
        idx = VectorIndex(dimension=2)
        idx.add(
            [Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt"))],
            [[1.0, 0.0]],
        )
        with pytest.raises(ValueError) as exc:
            idx.search([1.0, 0.0, 0.0])
        assert "Query dimension 3 != index dimension 2" in str(exc.value)

    def test_search_identical_vectors(self):
        """Identical vectors have similarity 1.0."""
        idx = VectorIndex(dimension=3)
        idx.add(
            [Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt"))],
            [[1.0, 2.0, 3.0]],
        )

        results = idx.search([1.0, 2.0, 3.0], top_k=1)
        assert len(results) == 1
        assert results[0].score == pytest.approx(1.0, abs=1e-5)

    def test_search_opposite_vectors(self):
        """Opposite vectors have similarity -1.0."""
        idx = VectorIndex(dimension=2)
        idx.add(
            [Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt"))],
            [[1.0, 0.0]],
        )

        results = idx.search([-1.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0].score == pytest.approx(-1.0, abs=1e-5)

    def test_search_zero_vector(self):
        """Zero query vector doesn't crash (epsilon prevents div by zero)."""
        idx = VectorIndex(dimension=2)
        idx.add(
            [Chunk(id="doc#1", text="a", meta=ChunkMeta(source="a.txt"))],
            [[1.0, 0.0]],
        )

        # Should not raise
        results = idx.search([0.0, 0.0], top_k=1)
        assert len(results) == 1


class TestVectorIndexPersistence:
    """Tests for save/load."""

    def test_save_creates_directory(self, tmp_path):
        """Save creates parent directories."""
        idx = VectorIndex(dimension=2)
        idx.add(
            [Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt"))],
            [[1.0, 0.0]],
        )

        save_path = tmp_path / "nested" / "index"
        idx.save(save_path)

        assert save_path.exists()
        assert (save_path / "vectors.npy").exists()
        assert (save_path / "vector_meta.json").exists()

    def test_save_load_roundtrip(self, tmp_path):
        """Save and load preserves data."""
        idx = VectorIndex(dimension=3)
        chunks = [
            Chunk(id="doc#1", text="first", meta=ChunkMeta(source="a.txt")),
            Chunk(id="doc#2", text="second", meta=ChunkMeta(source="b.txt")),
        ]
        vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        idx.add(chunks, vectors)

        save_path = tmp_path / "index"
        idx.save(save_path)

        # Load into fresh index
        idx2 = VectorIndex()
        idx2.load(save_path)

        assert idx2.dimension == 3
        assert idx2._chunk_ids == ["doc#1", "doc#2"]
        assert idx2._chunks["doc#1"].text == "first"
        assert idx2._chunks["doc#2"].text == "second"
        assert idx2._vectors is not None
        assert idx2._vectors.shape == (2, 3)
        np.testing.assert_array_equal(idx2._vectors[0], [1.0, 0.0, 0.0])

    def test_load_missing_files(self, tmp_path):
        """Load missing files raises FileNotFoundError."""
        idx = VectorIndex()
        with pytest.raises(FileNotFoundError) as exc:
            idx.load(tmp_path / "nonexistent")
        assert "Vector index not found" in str(exc.value)

    def test_load_partial_files(self, tmp_path):
        """Load with only one file missing raises FileNotFoundError."""
        idx = VectorIndex()
        (tmp_path / "vectors.npy").write_text("")
        with pytest.raises(FileNotFoundError):
            idx.load(tmp_path)

    def test_save_empty_index(self, tmp_path):
        """Save empty index creates meta file; vectors.npy may or may not exist."""
        idx = VectorIndex(dimension=2)
        save_path = tmp_path / "index"
        idx.save(save_path)

        assert (save_path / "vector_meta.json").exists()

        # Load back - may fail if vectors.npy is expected but missing
        idx2 = VectorIndex()
        if (save_path / "vectors.npy").exists():
            idx2.load(save_path)
        else:
            # If vectors.npy doesn't exist for empty index, load should handle it
            with pytest.raises(FileNotFoundError):
                idx2.load(save_path)
            return

        assert idx2.dimension == 2
        assert idx2._chunk_ids == []

    def test_meta_content(self, tmp_path):
        """Meta JSON has correct structure."""
        idx = VectorIndex(dimension=5)
        chunk = Chunk(id="doc#1", text="hello", meta=ChunkMeta(source="a.txt"))
        idx.add([chunk], [[1.0, 2.0, 3.0, 4.0, 5.0]])

        save_path = tmp_path / "index"
        idx.save(save_path)

        with open(save_path / "vector_meta.json") as f:
            meta = json.load(f)

        assert meta["dimension"] == 5
        assert meta["chunk_ids"] == ["doc#1"]
        assert "doc#1" in meta["chunks"]
        assert meta["chunks"]["doc#1"]["text"] == "hello"
