"""ragent mcp subcommand."""


def register(subparsers):
    parser = subparsers.add_parser("mcp", help="MCP server management")
    mcp_sub = parser.add_subparsers(dest="mcp_cmd")

    list_p = mcp_sub.add_parser("list", help="List MCP servers")
    list_p.set_defaults(func=list_servers)

    test_p = mcp_sub.add_parser("test", help="Test an MCP server")
    test_p.add_argument("name")
    test_p.set_defaults(func=test_server)

    add_p = mcp_sub.add_parser("add", help="Add an MCP server")
    add_p.add_argument("name")
    add_p.add_argument("command")
    add_p.set_defaults(func=add_server)


def run(args):
    pass


def list_servers(args):
    print("MCP servers: (stub)")


def test_server(args):
    print(f"Testing MCP server {args.name} ... (stub)")


def add_server(args):
    print(f"Adding MCP server {args.name} ... (stub)")
