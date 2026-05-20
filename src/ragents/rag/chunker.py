"""Semantic chunker with heading/code/table detection."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from ragents.schema.chunk import Chunk, ChunkMeta
from ragents.utils.logger import logger


class BaseChunker(ABC):
    """Abstract base for chunking strategies."""

    @abstractmethod
    def chunk(self, text: str, source: str) -> list[Chunk]:
        """Split text into semantic chunks."""
        ...

    def chunk_file(self, path: Path) -> list[Chunk]:
        """Read file and chunk it."""
        text = path.read_text(encoding="utf-8")
        return self.chunk(text, str(path))


class MarkdownChunker(BaseChunker):
    """Split Markdown on headings."""

    HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def chunk(self, text: str, source: str) -> list[Chunk]:
        matches = list(self.HEADING_RE.finditer(text))
        if not matches:
            return self._single_chunk(text, source)

        chunks: list[Chunk] = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk_text = text[start:end].strip()
            if chunk_text:
                line_start = text[:start].count("\n") + 1
                line_end = text[:end].count("\n") + 1
                chunks.append(
                    Chunk(
                        id=f"{source}#{i}",
                        text=chunk_text,
                        meta=ChunkMeta(
                            source=source,
                            start_line=line_start,
                            end_line=line_end,
                            extra={"heading": match.group(2).strip()},
                        ),
                    )
                )
        return chunks

    def _single_chunk(self, text: str, source: str) -> list[Chunk]:
        stripped = text.strip()
        if not stripped:
            return []
        lines = text.splitlines()
        return [
            Chunk(
                id=f"{source}#0",
                text=stripped,
                meta=ChunkMeta(
                    source=source,
                    start_line=1,
                    end_line=max(len(lines), 1),
                ),
            )
        ]


class CodeChunker(BaseChunker):
    """Split code on function/class boundaries."""

    # Python: def / class / async def
    # JS/TS: function / class / const/let/var arrow functions / async function
    # Go: func
    # Rust: fn / impl / trait
    PATTERNS = {
        ".py": re.compile(r"^\s*(?:async\s+)?def\s+|^\s*class\s+", re.MULTILINE),
        ".js": re.compile(
            r"^\s*(?:async\s+)?function\s+|^\s*class\s+|"
            r"^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\(",
            re.MULTILINE,
        ),
        ".ts": re.compile(
            r"^\s*(?:async\s+)?function\s+|^\s*class\s+|^\s*interface\s+|"
            r"^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\(",
            re.MULTILINE,
        ),
        ".go": re.compile(r"^\s*func\s+", re.MULTILINE),
        ".rs": re.compile(r"^\s*(?:fn|impl|trait)\s+", re.MULTILINE),
    }

    def chunk(self, text: str, source: str) -> list[Chunk]:
        ext = Path(source).suffix.lower()
        pattern = self.PATTERNS.get(ext)

        if not pattern:
            # Fallback to fixed-size for unknown languages
            return FixedSizeChunker().chunk(text, source)

        matches = list(pattern.finditer(text))
        if not matches:
            return self._single_chunk(text, source)

        chunks: list[Chunk] = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk_text = text[start:end].strip()
            if chunk_text:
                line_start = text[:start].count("\n") + 1
                line_end = text[:end].count("\n") + 1
                # Extract first line as name hint
                first_line = chunk_text.splitlines()[0] if chunk_text else ""
                chunks.append(
                    Chunk(
                        id=f"{source}#{i}",
                        text=chunk_text,
                        meta=ChunkMeta(
                            source=source,
                            start_line=line_start,
                            end_line=line_end,
                            extra={
                                "language": ext.lstrip("."),
                                "signature": first_line[:100],
                            },
                        ),
                    )
                )
        return chunks

    def _single_chunk(self, text: str, source: str) -> list[Chunk]:
        stripped = text.strip()
        if not stripped:
            return []
        lines = text.splitlines()
        return [
            Chunk(
                id=f"{source}#0",
                text=stripped,
                meta=ChunkMeta(
                    source=source,
                    start_line=1,
                    end_line=max(len(lines), 1),
                ),
            )
        ]


class FixedSizeChunker(BaseChunker):
    """Split text into fixed-size chunks with overlap."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, source: str) -> list[Chunk]:
        if not text.strip():
            return []

        chunks: list[Chunk] = []
        start = 0
        idx = 0
        lines = text.splitlines()
        line_offsets = [0]
        for line in lines:
            line_offsets.append(line_offsets[-1] + len(line) + 1)

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            # Extend to word boundary
            if end < len(text):
                while end > start and text[end] not in " \n\t":
                    end -= 1
                if end == start:
                    end = min(start + self.chunk_size, len(text))

            chunk_text = text[start:end].strip()
            if chunk_text:
                # Find line numbers
                line_start = text[:start].count("\n") + 1
                line_end = text[:end].count("\n") + 1
                chunks.append(
                    Chunk(
                        id=f"{source}#{idx}",
                        text=chunk_text,
                        meta=ChunkMeta(
                            source=source,
                            start_line=line_start,
                            end_line=line_end,
                        ),
                    )
                )
                idx += 1

            start = end - self.overlap
            if start <= 0 or start >= len(text):
                break
            # Prevent infinite loop when remaining text is shorter than overlap
            if end - start >= len(text) - start:
                break

        return chunks


class Chunker:
    """Auto-selects chunking strategy based on file type."""

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._markdown = MarkdownChunker()
        self._code = CodeChunker()
        self._fixed = FixedSizeChunker(chunk_size, overlap)

    def chunk(self, text: str, source: str) -> list[Chunk]:
        """Chunk text using auto-selected strategy."""
        strategy = self._select_strategy(text, source)
        logger.info(
            "chunking",
            source=source,
            strategy=strategy.__class__.__name__,
        )
        chunks = strategy.chunk(text, source)
        logger.info(
            "chunked",
            source=source,
            chunk_count=len(chunks),
        )
        return chunks

    def chunk_file(self, path: Path) -> list[Chunk]:
        """Read and chunk a file."""
        text = path.read_text(encoding="utf-8")
        return self.chunk(text, str(path))

    def _select_strategy(self, text: str, source: str) -> BaseChunker:
        """Select chunking strategy based on file type and content."""
        source_lower = source.lower()

        # Markdown
        if source_lower.endswith(".md") or "## " in text[:1000]:
            return self._markdown

        # Code files
        code_exts = {".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c", ".h"}
        if any(source_lower.endswith(ext) for ext in code_exts):
            return self._code

        # Default: fixed-size
        return self._fixed
