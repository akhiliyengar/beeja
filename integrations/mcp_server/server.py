"""builder MCP server entry-point shim.

The actual implementation lives in `skill.mcp_server`. This module exists for
parity with the tarball layout (`integrations/mcp_server/server.py`) and lets
clients launch the server via either:

    python -m skill.mcp_server                          # canonical
    python -m integrations.mcp_server.server            # tarball-compatible
"""

from skill.mcp_server import main

if __name__ == "__main__":
    main()
