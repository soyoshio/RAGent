"""Chunker unit tests.

Covers all chunking strategies in ragents.rag.chunker:
- MarkdownChunker (heading detection, fallback, line numbers, metadata)
- CodeChunker (Python/JS/TS/Go/Rust, unknown lang fallback, no-match fallback)
- FixedSizeChunker (splitting, overlap, word boundaries, empty text)
- Chunker (auto-selection by extension and content, chunk_file)
"""

from __future__ import annotations

import pytest
from pathlib import Path

from ragents.rag.chunker import (
    BaseChunker,
    Chunker,
    CodeChunker,
    FixedSizeChunker,
    MarkdownChunker,
)
from ragents.schema.chunk import Chunk


# ---------------------------------------------------------------------------
# MarkdownChunker
# ---------------------------------------------------------------------------


class TestMarkdownChunker:
    def test_multiple_headings(self):
        text = "# Title\nContent 1\n## Section 2\nContent 2\n### Sub\nContent 3\n"
        chunks = MarkdownChunker().chunk(text, "doc.md")
        assert len(chunks) == 3
        assert chunks[0].meta.extra["heading"] == "Title"
        assert chunks[1].meta.extra["heading"] == "Section 2"
        assert chunks[2].meta.extra["heading"] == "Sub"

    def test_line_numbers(self):
        text = "# H1\nLine2\nLine3\n## H2\nLine5\n"
        chunks = MarkdownChunker().chunk(text, "doc.md")
        assert chunks[0].meta.start_line == 1
        assert chunks[0].meta.end_line == 4
        assert chunks[1].meta.start_line == 4
        assert chunks[1].meta.end_line == 6

    def test_no_headings_fallback(self):
        text = "Just some plain text.\nNo headings here.\n"
        chunks = MarkdownChunker().chunk(text, "doc.md")
        assert len(chunks) == 1
        assert chunks[0].id == "doc.md#0"
        assert chunks[0].meta.start_line == 1
        assert chunks[0].meta.end_line == 2

    def test_single_heading(self):
        text = "# Only Heading\nSome content.\n"
        chunks = MarkdownChunker().chunk(text, "doc.md")
        assert len(chunks) == 1
        assert chunks[0].meta.extra["heading"] == "Only Heading"

    def test_heading_levels(self):
        text = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6\n"
        chunks = MarkdownChunker().chunk(text, "doc.md")
        assert len(chunks) == 6
        for i, c in enumerate(chunks):
            assert c.meta.extra["heading"] == f"H{i + 1}"

    def test_empty_text(self):
        chunks = MarkdownChunker().chunk("", "doc.md")
        assert chunks == []


# ---------------------------------------------------------------------------
# CodeChunker - Python
# ---------------------------------------------------------------------------


class TestCodeChunkerPython:
    def test_functions_and_classes(self):
        text = (
            "def hello():\n"
            "    return 'world'\n"
            "\n"
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 42\n"
            "\n"
            "async def async_fn():\n"
            "    pass\n"
        )
        chunks = CodeChunker().chunk(text, "test.py")
        # CodeChunker matches all def/class at top level and nested
        assert len(chunks) == 4
        assert "def hello():" in chunks[0].text
        assert "class Foo:" in chunks[1].text
        assert "def bar(self):" in chunks[2].text
        assert "async def async_fn():" in chunks[3].text

    def test_line_numbers(self):
        text = (
            "def a():\n"
            "    pass\n"
            "\n"
            "def b():\n"
            "    pass\n"
        )
        chunks = CodeChunker().chunk(text, "test.py")
        assert chunks[0].meta.start_line == 1
        assert chunks[0].meta.end_line == 3
        # def b() starts at line 3 because the empty line before it is part of chunk 0's text range
        assert chunks[1].meta.start_line == 3
        assert chunks[1].meta.end_line == 6

    def test_signature_extraction(self):
        text = "def my_function(x: int) -> str:\n    return str(x)\n"
        chunks = CodeChunker().chunk(text, "test.py")
        assert chunks[0].meta.extra["signature"] == "def my_function(x: int) -> str:"
        assert chunks[0].meta.extra["language"] == "py"

    def test_no_matches_fallback(self):
        text = "# Just a comment\nx = 1\ny = 2\n"
        chunks = CodeChunker().chunk(text, "test.py")
        assert len(chunks) == 1
        assert chunks[0].id == "test.py#0"

    def test_empty_text(self):
        chunks = CodeChunker().chunk("", "test.py")
        assert chunks == []

    def test_nested_methods(self):
        """Methods inside classes are separate chunks."""
        text = (
            "class Outer:\n"
            "    def method1(self):\n"
            "        pass\n"
            "    def method2(self):\n"
            "        pass\n"
        )
        chunks = CodeChunker().chunk(text, "test.py")
        assert len(chunks) == 3
        assert "class Outer:" in chunks[0].text
        assert "def method1" in chunks[1].text
        assert "def method2" in chunks[2].text


# ---------------------------------------------------------------------------
# CodeChunker - JavaScript / TypeScript
# ---------------------------------------------------------------------------


class TestCodeChunkerJS:
    def test_js_function(self):
        text = "function hello() {\n    return 'world';\n}\n"
        chunks = CodeChunker().chunk(text, "test.js")
        assert len(chunks) == 1
        assert "function hello()" in chunks[0].text

    def test_js_class(self):
        text = "class Foo {\n    bar() {\n        return 42;\n    }\n}\n"
        chunks = CodeChunker().chunk(text, "test.js")
        assert len(chunks) == 1
        assert "class Foo" in chunks[0].text

    def test_js_arrow_function(self):
        text = "const hello = () => {\n    return 'world';\n};\n"
        chunks = CodeChunker().chunk(text, "test.js")
        assert len(chunks) == 1
        assert "const hello = ()" in chunks[0].text

    def test_ts_interface(self):
        text = (
            "interface User {\n"
            "    name: string;\n"
            "}\n"
            "function greet(u: User) {\n"
            "    return u.name;\n"
            "}\n"
        )
        chunks = CodeChunker().chunk(text, "test.ts")
        assert len(chunks) == 2
        assert "interface User" in chunks[0].text
        assert "function greet" in chunks[1].text


# ---------------------------------------------------------------------------
# CodeChunker - Go / Rust
# ---------------------------------------------------------------------------


class TestCodeChunkerGoRust:
    def test_go_functions(self):
        text = (
            "func Hello() string {\n"
            "    return \"world\"\n"
            "}\n"
            "\n"
            "func Add(a, b int) int {\n"
            "    return a + b\n"
            "}\n"
        )
        chunks = CodeChunker().chunk(text, "test.go")
        assert len(chunks) == 2
        assert "func Hello()" in chunks[0].text
        assert "func Add(a, b int)" in chunks[1].text

    def test_rust_functions(self):
        text = (
            "fn hello() -> String {\n"
            "    \"world\".to_string()\n"
            "}\n"
            "\n"
            "fn add(a: i32, b: i32) -> i32 {\n"
            "    a + b\n"
            "}\n"
        )
        chunks = CodeChunker().chunk(text, "test.rs")
        assert len(chunks) == 2
        assert "fn hello()" in chunks[0].text
        assert "fn add(a: i32" in chunks[1].text

    def test_rust_impl(self):
        text = (
            "impl MyStruct {\n"
            "    fn method(&self) {}\n"
            "}\n"
            "\n"
            "trait MyTrait {\n"
            "    fn required(&self);\n"
            "}\n"
        )
        chunks = CodeChunker().chunk(text, "test.rs")
        # CodeChunker matches fn/impl/trait at any indentation level
        assert len(chunks) == 4
        assert "impl MyStruct" in chunks[0].text
        assert "fn method" in chunks[1].text
        assert "trait MyTrait" in chunks[2].text
        assert "fn required" in chunks[3].text


# ---------------------------------------------------------------------------
# CodeChunker - Unknown language fallback
# ---------------------------------------------------------------------------


class TestCodeChunkerFallback:
    def test_unknown_extension_uses_fixed_size(self):
        text = "a " * 1000
        chunks = CodeChunker().chunk(text, "test.unknown")
        # Should use FixedSizeChunker which produces multiple chunks for long text
        assert len(chunks) > 1

    def test_java_uses_fixed_size_fallback(self):
        """Java is in code_exts but not in PATTERNS, so falls back to FixedSize."""
        text = "public class Hello {\n    public static void main() {}\n}\n"
        chunks = CodeChunker().chunk(text, "test.java")
        # Java is in code_exts set but not in PATTERNS, so FixedSizeChunker is used
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# FixedSizeChunker
# ---------------------------------------------------------------------------


class TestFixedSizeChunker:
    def test_basic_splitting(self):
        text = "word " * 200  # ~1000 chars
        chunker = FixedSizeChunker(chunk_size=300, overlap=30)
        chunks = chunker.chunk(text, "doc.txt")
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.text) <= 300

    def test_overlap(self):
        text = "word " * 200
        chunker = FixedSizeChunker(chunk_size=300, overlap=50)
        chunks = chunker.chunk(text, "doc.txt")
        if len(chunks) >= 2:
            # Some overlap should exist between consecutive chunks
            text1 = chunks[0].text
            text2 = chunks[1].text
            # Check that at least some words are shared
            words1 = set(text1.split())
            words2 = set(text2.split())
            assert len(words1 & words2) > 0

    def test_word_boundary(self):
        text = "hello world foo bar baz qux"
        chunker = FixedSizeChunker(chunk_size=20, overlap=5)
        chunks = chunker.chunk(text, "doc.txt")
        assert len(chunks) >= 1
        # Each chunk should not break words at the end
        for c in chunks:
            assert not c.text.endswith("wo")  # partial word

    def test_empty_text(self):
        chunker = FixedSizeChunker()
        chunks = chunker.chunk("", "doc.txt")
        assert chunks == []

    def test_whitespace_only(self):
        chunker = FixedSizeChunker()
        chunks = chunker.chunk("   \n\t  \n", "doc.txt")
        assert chunks == []

    def test_line_numbers(self):
        text = "line1\nline2\nline3\nline4\nline5\n"
        chunker = FixedSizeChunker(chunk_size=20, overlap=5)
        chunks = chunker.chunk(text, "doc.txt")
        assert len(chunks) >= 1
        assert chunks[0].meta.start_line == 1

    def test_single_short_text(self):
        text = "Short text."
        chunker = FixedSizeChunker(chunk_size=500, overlap=50)
        chunks = chunker.chunk(text, "doc.txt")
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."

    def test_chunk_ids_increment(self):
        text = "word " * 200
        chunker = FixedSizeChunker(chunk_size=200, overlap=20)
        chunks = chunker.chunk(text, "doc.txt")
        for i, c in enumerate(chunks):
            assert c.id == f"doc.txt#{i}"


# ---------------------------------------------------------------------------
# Chunker (auto-selection)
# ---------------------------------------------------------------------------


class TestChunkerAutoSelection:
    def test_selects_markdown_by_extension(self):
        chunker = Chunker()
        strategy = chunker._select_strategy("# Hello", "doc.md")
        assert isinstance(strategy, MarkdownChunker)

    def test_selects_markdown_by_content(self):
        chunker = Chunker()
        strategy = chunker._select_strategy("## Heading\nContent", "doc.txt")
        assert isinstance(strategy, MarkdownChunker)

    def test_selects_code_python(self):
        chunker = Chunker()
        strategy = chunker._select_strategy("def hello(): pass", "script.py")
        assert isinstance(strategy, CodeChunker)

    def test_selects_code_javascript(self):
        chunker = Chunker()
        strategy = chunker._select_strategy("function hello() {}", "script.js")
        assert isinstance(strategy, CodeChunker)

    def test_selects_code_typescript(self):
        chunker = Chunker()
        strategy = chunker._select_strategy("interface Foo {}", "script.ts")
        assert isinstance(strategy, CodeChunker)

    def test_selects_code_go(self):
        chunker = Chunker()
        strategy = chunker._select_strategy("func main() {}", "main.go")
        assert isinstance(strategy, CodeChunker)

    def test_selects_code_rust(self):
        chunker = Chunker()
        strategy = chunker._select_strategy("fn main() {}", "main.rs")
        assert isinstance(strategy, CodeChunker)

    def test_selects_fixed_size_for_plain_text(self):
        chunker = Chunker()
        strategy = chunker._select_strategy("Just plain text.", "doc.txt")
        assert isinstance(strategy, FixedSizeChunker)

    def test_chunk_method_returns_chunks(self):
        chunker = Chunker()
        chunks = chunker.chunk("# Title\nContent", "doc.md")
        assert len(chunks) >= 1
        assert isinstance(chunks[0], Chunk)

    def test_chunk_file(self, tmp_path: Path):
        file_path = tmp_path / "test.md"
        file_path.write_text("# Hello\nWorld\n")
        chunker = Chunker()
        chunks = chunker.chunk_file(file_path)
        assert len(chunks) == 1
        assert chunks[0].meta.source == str(file_path)

    def test_chunk_file_python(self, tmp_path: Path):
        file_path = tmp_path / "test.py"
        file_path.write_text("def hello():\n    return 'world'\n")
        chunker = Chunker()
        chunks = chunker.chunk_file(file_path)
        assert len(chunks) == 1
        assert "def hello():" in chunks[0].text


# ---------------------------------------------------------------------------
# BaseChunker
# ---------------------------------------------------------------------------


class TestBaseChunker:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BaseChunker()

    def test_chunk_file_on_concrete(self, tmp_path: Path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("hello world")
        chunker = FixedSizeChunker()
        chunks = chunker.chunk_file(file_path)
        assert len(chunks) == 1
        assert chunks[0].text == "hello world"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_markdown_with_code_blocks(self):
        text = (
            "# Section 1\n"
            "```python\n"
            "def hello():\n"
            "    pass\n"
            "```\n"
            "## Section 2\n"
            "More text.\n"
        )
        chunks = MarkdownChunker().chunk(text, "doc.md")
        assert len(chunks) == 2
        assert "Section 1" in chunks[0].text
        assert "Section 2" in chunks[1].text

    def test_code_with_decorators(self):
        """Python decorators before functions — decorator is not part of the function chunk."""
        text = (
            "@decorator\n"
            "def func():\n"
            "    pass\n"
        )
        chunks = CodeChunker().chunk(text, "test.py")
        # Pattern matches def, not @decorator; decorator line is excluded
        assert len(chunks) == 1
        assert "def func():" in chunks[0].text
        assert "@decorator" not in chunks[0].text

    def test_unicode_content(self):
        text = "# 标题\n内容：你好世界 🌍\n## 第二节\n更多内容\n"
        chunks = MarkdownChunker().chunk(text, "doc.md")
        assert len(chunks) == 2
        assert "你好世界" in chunks[0].text

    def test_very_long_single_line(self):
        text = "a" * 2000
        chunker = FixedSizeChunker(chunk_size=500, overlap=50)
        chunks = chunker.chunk(text, "doc.txt")
        assert len(chunks) > 1
        # When word boundary can't be found, should force split at chunk_size
        for c in chunks:
            assert len(c.text) <= 500
