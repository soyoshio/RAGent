"""ragent query subcommand — direct RAG query."""

from __future__ import annotations

import sys
from pathlib import Path

from ragents.cli.renderers.rich_renderer import render_markdown
from ragents.errors import RAGentError
from ragents.rag import (
    Chunker,
    FusionRetriever,
    KeywordIndex,
    KeywordRetriever,
    VectorIndex,
    VectorRetriever,
    create_embedder,
)
from ragents.utils.config import create_settings
from ragents.utils.logger import logger


SYSTEM_PROMPT = """You are a helpful coding assistant. Answer the user's question based on the provided code context.

Guidelines:
- Be concise but thorough
- Cite specific files and line numbers when referencing code
- If the context doesn't contain enough information, say so honestly
- Format code snippets in markdown code blocks with language tags
"""


def _build_prompt(query: str, chunks: list) -> str:
    """Build the prompt with retrieved chunks."""
    context_parts = []
    for i, rc in enumerate(chunks, 1):
        chunk = rc.chunk
        meta = chunk.meta
        source = meta.source
        lines = ""
        if meta.start_line and meta.end_line:
            lines = f" (lines {meta.start_line}-{meta.end_line})"
        context_parts.append(
            f"[{i}] **{source}**{lines}\n```\n{chunk.text}\n```"
        )

    context = "\n\n".join(context_parts)

    return f"""{SYSTEM_PROMPT}

## Context

{context}

## Question

{query}

## Answer

"""


def _load_index(index_path: Path):
    """Load vector and keyword indexes from disk."""
    vector_index = VectorIndex()
    keyword_index = KeywordIndex()

    vector_index.load(index_path)
    keyword_index.load(index_path)

    return vector_index, keyword_index


def register(subparsers):
    parser = subparsers.add_parser("query", help="Run a direct RAG query")
    parser.add_argument("q", help="Query string")
    parser.add_argument(
        "--index",
        "-i",
        default="index",
        help="Path to index directory (default: index)",
    )
    parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve (default: 5)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show retrieval details",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "local", "deepseek"],
        help="LLM provider override",
    )
    parser.add_argument(
        "--model",
        help="LLM model override",
    )
    parser.set_defaults(func=run)


def run(args):
    query = args.q
    index_path = Path(args.index)
    verbose = args.verbose

    # Load settings
    cli_overrides = {}
    if args.provider:
        cli_overrides["default_llm_provider"] = args.provider
    if args.model:
        cli_overrides["llm_model"] = args.model

    settings = create_settings(cli_overrides=cli_overrides)

    # Check index exists
    if not index_path.exists():
        print(
            f"Error: Index not found at '{index_path}'.\n"
            f"Run 'ragent index <path>' first to build an index.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # Load embedder
        embedder = create_embedder(settings)

        # Load indexes
        vector_index, keyword_index = _load_index(index_path)

        # Build retrievers
        retrievers = {
            "vector": VectorRetriever(vector_index, embedder),
            "keyword": KeywordRetriever(keyword_index),
        }
        fusion = FusionRetriever(retrievers, rrf_k=settings.rag.rrf_k)

        # Retrieve chunks
        chunks = fusion.retrieve(query, top_k=args.top_k)

        if verbose:
            print(f"Retrieved {len(chunks)} chunks:")
            for rc in chunks:
                print(f"  - {rc.chunk.id} (score: {rc.score:.4f})")
            print()

        if not chunks:
            print("No relevant chunks found. Try a different query or rebuild the index.")
            return

        # Synthesize answer with LLM
        prompt = _build_prompt(query, chunks)

        if verbose:
            print(f"Prompt length: {len(prompt)} chars")
            print()

        # Create LLM provider
        from ragents.llm import PROVIDER_MAP

        provider_name = settings.default_llm_provider
        provider_cls = PROVIDER_MAP.get(provider_name)
        if not provider_cls:
            print(f"Error: Unknown provider '{provider_name}'", file=sys.stderr)
            sys.exit(1)

        # Build provider config
        if provider_name in ("openai", "deepseek"):
            if settings.deepseek_api_key:
                provider = provider_cls(
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_base_url_openai,
                    model=settings.deepseek_model,
                )
            else:
                provider = provider_cls(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                    model=settings.openai_model,
                )
        elif provider_name == "anthropic":
            if settings.deepseek_api_key:
                provider = provider_cls(
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_base_url_anthropic,
                    model=settings.deepseek_model,
                )
            else:
                provider = provider_cls(
                    api_key=settings.anthropic_api_key,
                    base_url=settings.anthropic_base_url,
                    model=settings.anthropic_model,
                )
        else:
            provider = provider_cls()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        answer = provider.chat(messages, temperature=0.7)

        # Render answer
        render_markdown(answer)

        # Show sources
        print("\n---\n**Sources:**")
        for rc in chunks:
            meta = rc.chunk.meta
            lines = ""
            if meta.start_line and meta.end_line:
                lines = f" (L{meta.start_line}-{meta.end_line})"
            print(f"- `{meta.source}`{lines}")

    except RAGentError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        logger.error("query_failed", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)
