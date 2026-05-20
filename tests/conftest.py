"""pytest global fixtures."""

import pytest
from ragents.schema.chunk import Chunk, ChunkMeta


@pytest.fixture
def sample_chunk():
    return Chunk(
        id="test#1",
        text="def hello():\n    return 'world'",
        meta=ChunkMeta(source="test.py", start_line=1, end_line=2),
    )
