"""Test setup: stub the `mcp` package so the pure business logic can be
tested without installing the MCP SDK or starting a server."""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class _FakeFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        return lambda fn: fn

    def run(self, *args, **kwargs):
        pass


if "mcp" not in sys.modules:
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = _FakeFastMCP
    server = types.ModuleType("mcp.server")
    server.fastmcp = fastmcp
    root = types.ModuleType("mcp")
    root.server = server
    sys.modules.update({"mcp": root, "mcp.server": server, "mcp.server.fastmcp": fastmcp})
