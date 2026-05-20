"""Sample chunks for tests."""

from ragents.schema.chunk import Chunk, ChunkMeta


SAMPLE_CHUNKS = [
    Chunk(
        id="sample#1",
        text="React Hooks allow you to use state in functional components.",
        meta=ChunkMeta(source="react_hooks_guide.md"),
    ),
    Chunk(
        id="sample#2",
        text="useEffect is used for side effects in functional components.",
        meta=ChunkMeta(source="react_hooks_guide.md"),
    ),
]
