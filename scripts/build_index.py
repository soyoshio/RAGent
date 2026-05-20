"""Standalone index build script."""

import argparse
import json
from pathlib import Path

from ragents.rag.chunker import Chunker
from ragents.schema.chunk import ChunkMeta


def main():
    parser = argparse.ArgumentParser(description="Build chunk index from documents")
    parser.add_argument("input", help="Input directory or file")
    parser.add_argument("--output", default="index/chunks.json", help="Output index path")
    args = parser.parse_args()

    chunker = Chunker()
    input_path = Path(args.input)
    chunks = []
    if input_path.is_dir():
        for f in input_path.rglob("*.md"):
            chunks.extend(chunker.chunk(f.read_text(), source=str(f)))
    else:
        chunks.extend(chunker.chunk(input_path.read_text(), source=str(input_path)))

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps([c.model_dump() for c in chunks], ensure_ascii=False, indent=2)
    )
    print(f"Index written to {args.output} ({len(chunks)} chunks)")


if __name__ == "__main__":
    main()
