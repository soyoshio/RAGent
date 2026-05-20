"""ragent chat subcommand."""


def register(subparsers):
    parser = subparsers.add_parser("chat", help="Start an interactive chat session")
    parser.set_defaults(func=run)


def run(args):
    print("Chat session started. (stub)")
