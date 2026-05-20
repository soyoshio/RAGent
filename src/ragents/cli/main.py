"""argparse / click / typer entry for CLI."""

import argparse
import sys

from ragents.cli.commands import chat, index, query, mcp


def main():
    parser = argparse.ArgumentParser(prog="ragent", description="RAGent CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Register subcommands
    chat.register(subparsers)
    index.register(subparsers)
    query.register(subparsers)
    mcp.register(subparsers)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)
