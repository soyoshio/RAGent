"""ragent index subcommand — build searchable index from codebase."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from ragents.errors import RAGentError
from ragents.rag import Chunker, KeywordIndex, VectorIndex, create_embedder
from ragents.utils.config import create_settings
from ragents.utils.logger import logger

# Supported file extensions for indexing
SUPPORTED_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".md",
    ".rst",
    ".txt",
}


def _scan_files(root: Path) -> list[Path]:
    """Recursively scan for supported files."""
    files = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
            # Skip common non-source directories
            parts = path.parts
            skip_dirs = {
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                "node_modules",
                ".pytest_cache",
                "dist",
                "build",
                ".eggs",
                ".tox",
            }
            if any(d in parts for d in skip_dirs):
                continue
            files.append(path)
    return sorted(files)


def _file_checksum(path: Path) -> str:
    """Compute MD5 checksum of file contents."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def _load_manifest(index_path: Path) -> dict:
    """Load index manifest if it exists."""
    manifest_file = index_path / "manifest.json"
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}}


def _save_manifest(index_path: Path, manifest: dict) -> None:
    """Save index manifest."""
    manifest_file = index_path / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def register(subparsers):
    parser = subparsers.add_parser("index", help="Index documents for retrieval")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to codebase directory (default: current directory)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="index",
        help="Output index directory (default: index)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Chunk size for fixed-size chunking (default: 500)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Chunk overlap (default: 50)",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force rebuild (ignore incremental)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress",
    )
    parser.set_defaults(func=run)


def run(args):
    root = Path(args.path).resolve()
    index_path = Path(args.output)
    verbose = args.verbose
    force = args.force

    if not root.exists():
        print(f"Error: Path '{root}' does not exist.", file=sys.stderr)
        sys.exit(1)

    settings = create_settings()

    # Scan files
    print(f"Scanning {root}...")
    files = _scan_files(root)
    print(f"Found {len(files)} supported files.")

    if not files:
        print("No supported files found. Nothing to index.")
        return

    # Load manifest for incremental indexing
    manifest = _load_manifest(index_path)
    indexed_files = manifest.get("files", {})

    # Filter to only changed files
    if not force:
        changed_files = []
        for f in files:
            checksum = _file_checksum(f)
            rel_path = str(f.relative_to(root))
            if indexed_files.get(rel_path) != checksum:
                changed_files.append(f)
        if changed_files:
            print(f"{len(changed_files)} files changed since last index.")
        files = changed_files

    if not files:
        print("All files are up to date. Nothing to index.")
        return

    try:
        # Initialize components
        chunker = Chunker(
            chunk_size=args.chunk_size,
            overlap=args.chunk_overlap,
        )
        embedder = create_embedder(settings)

        # Load existing indexes if available
        vector_index = VectorIndex(dimension=embedder.dimension)
        keyword_index = KeywordIndex()

        if index_path.exists() and not force:
            try:
                vector_index.load(index_path)
                keyword_index.load(index_path)
                print("Loaded existing index.")
            except FileNotFoundError:
                pass

        # Index files
        total_chunks = 0
        for i, file_path in enumerate(files, 1):
            if verbose:
                print(f"[{i}/{len(files)}] {file_path}")
            else:
                # Simple progress
                if i % 10 == 0 or i == len(files):
                    print(f"Indexing... {i}/{len(files)} files", end="\r")

            try:
                text = file_path.read_text(encoding="utf-8")
                chunks = chunker.chunk(text, str(file_path))

                if chunks:
                    # Embed chunks
                    texts = [c.text for c in chunks]
                    vectors = embedder.embed(texts)

                    # Add to indexes
                    vector_index.add(chunks, vectors)
                    keyword_index.add(chunks)

                    total_chunks += len(chunks)

                # Update manifest
                rel_path = str(file_path.relative_to(root))
                manifest["files"][rel_path] = _file_checksum(file_path)

            except Exception as e:
                logger.error(
                    "index_file_failed",
                    path=str(file_path),
                    error=str(e),
                )
                if verbose:
                    print(f"  Warning: Failed to index {file_path}: {e}")

        print()  # Newline after progress

        # Save indexes
        index_path.mkdir(parents=True, exist_ok=True)
        vector_index.save(index_path)
        keyword_index.save(index_path)
        _save_manifest(index_path, manifest)

        print(f"Index built: {len(files)} files, {total_chunks} chunks.")
        print(f"Index saved to: {index_path.resolve()}")

    except RAGentError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error("index_failed", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
