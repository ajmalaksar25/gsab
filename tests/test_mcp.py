"""The MCP server registers its tools. Skipped unless the `mcp` extra is installed
(it requires Python 3.10+, so it's not part of the 3.9 CI matrix)."""

import asyncio

import pytest

pytest.importorskip("mcp")

from gsab.mcp import server  # noqa: E402

EXPECTED = {
    "create_sheet",
    "columns",
    "insert",
    "read",
    "update",
    "delete",
    "upsert",
    "query",
    "share",
}


def test_mcp_tools_registered():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert EXPECTED <= names
    assert server.mcp.name == "gsab"
