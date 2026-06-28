"""The MCP server registers its tools. Skipped unless the `mcp` extra is installed
(it requires Python 3.10+, so it's not part of the 3.9 CI matrix)."""

import asyncio

import pytest

pytest.importorskip("mcp")

from gsab import AccessPolicy  # noqa: E402
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


def test_read_only_server_omits_write_tools():
    m = server.build_server(read_only=True)
    names = {t.name for t in asyncio.run(m.list_tools())}
    assert {"columns", "read", "query"} <= names
    assert names.isdisjoint({"create_sheet", "insert", "update", "delete", "upsert", "share"})


def test_read_only_policy_omits_write_tools():
    m = server.build_server(policy=AccessPolicy(read_only=True))
    names = {t.name for t in asyncio.run(m.list_tools())}
    assert {"columns", "read", "query"} <= names
    assert names.isdisjoint({"create_sheet", "insert", "update", "delete", "upsert", "share"})


def test_attach_enforces_allowlist_before_network():
    from gsab import PolicyError

    server.build_server(policy=AccessPolicy(allowed_sheets=["ALLOWED"]))
    with pytest.raises(PolicyError):
        asyncio.run(server._attach("NOT_ALLOWED"))
    server.build_server()  # restore the permissive default for other tests
