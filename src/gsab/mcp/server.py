"""GSAB MCP server: expose a Google Sheet as a database to an MCP host.

Tools let an agent create a sheet, then insert / read / update / delete / query /
upsert / share it. Columns are treated as text (the agent works with strings); a
created sheet may declare a ``primary_key`` to unlock enforced uniqueness + upsert.

Auth uses the host's GSAB credentials (run ``gsab auth login`` once, or set
``GSAB_SERVICE_ACCOUNT``). Start with ``gsab mcp`` — add ``--read-only`` to expose
only the read / query tools (no writes, deletes or sharing).
"""

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ..core.connection import SheetConnection
from ..core.policy import AccessPolicy
from ..core.schema import Field, FieldType, Schema
from ..core.sheet_manager import SheetManager
from ..utils.errors import execute

# One SheetManager per spreadsheet id, built lazily from its live header row.
_managers: Dict[str, SheetManager] = {}

# The active AccessPolicy (set by build_server); guards every tool. Default = permissive.
_policy = AccessPolicy()


async def _attach(sheet_id: str) -> SheetManager:
    """Bind a SheetManager to an existing sheet, inferring text columns from its header."""
    if sheet_id in _managers:
        return _managers[sheet_id]
    _policy.ensure_sheet_allowed(sheet_id)  # gate attaching to an external sheet
    conn = SheetConnection()
    await conn.connect()
    meta = await execute(conn.service.spreadsheets().get(spreadsheetId=sheet_id), op="mcp_attach")
    tab = meta["sheets"][0]["properties"]["title"]
    res = await execute(
        conn.service.spreadsheets().values().get(spreadsheetId=sheet_id, range=f"{tab}!A1:Z1"),
        op="mcp_attach",
    )
    cols = (res.get("values") or [[]])[0]
    if not cols:
        raise ValueError(f"Sheet {sheet_id} has no header row to infer columns from.")
    schema = Schema(tab, [Field(c, FieldType.STRING, required=False) for c in cols])
    db = SheetManager(conn, schema, policy=_policy)
    db.sheet_id = sheet_id
    _managers[sheet_id] = db
    return db


def _url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


# --- Tools -------------------------------------------------------------------
# Plain functions, registered onto a server by build_server() so a read-only server
# can omit the write tools entirely.


async def create_sheet(
    title: str, columns: List[str], primary_key: Optional[str] = None
) -> Dict[str, str]:
    """Create a new Google Sheet (one tab) with these columns; return its id and URL.

    Set ``primary_key`` to one of the columns to enforce uniqueness on that column and
    enable ``upsert`` keyed on it. Returns ``{"sheet_id": ..., "url": ...}``.
    """
    fields = [
        Field(c, FieldType.STRING, primary_key=True)
        if c == primary_key
        else Field(c, FieldType.STRING, required=False)
        for c in columns
    ]
    db = SheetManager(SheetConnection(), Schema("data", fields), policy=_policy)
    sheet_id = await db.create_sheet(title)
    _managers[sheet_id] = db
    return {"sheet_id": sheet_id, "url": _url(sheet_id)}


async def columns(sheet_id: str) -> List[str]:
    """List the column names (header row) of a sheet."""
    db = await _attach(sheet_id)
    return [f.name for f in db.schema.fields]


async def insert(sheet_id: str, row: Dict[str, Any]) -> str:
    """Insert one row (a dict of column -> value) into the sheet."""
    db = await _attach(sheet_id)
    await db.insert({k: ("" if v is None else str(v)) for k, v in row.items()})
    return "inserted 1 row"


async def read(
    sheet_id: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Read rows as dicts. Optional ``filters`` = {column: value} (equality) or
    {column: {op: value}} with ops $eq $ne $gt $gte $lt $lte $in $nin $contains $regex.
    """
    db = await _attach(sheet_id)
    rows = await db.read(filters)
    return rows[:limit] if limit else rows


async def update(sheet_id: str, filters: Dict[str, Any], changes: Dict[str, Any]) -> str:
    """Update rows matching ``filters``, applying ``changes``. Returns the count changed."""
    db = await _attach(sheet_id)
    n = await db.update(filters, {k: str(v) for k, v in changes.items()})
    return f"updated {n} row(s)"


async def delete(sheet_id: str, filters: Dict[str, Any]) -> str:
    """Delete rows matching ``filters``. DESTRUCTIVE — permanently removes the matching
    rows and cannot be undone, so double-check ``filters`` before calling.
    """
    db = await _attach(sheet_id)
    n = await db.delete(filters)
    return f"Deleted {n} row(s) from '{db.schema.name}'. WARNING: permanent, cannot be undone."


async def upsert(sheet_id: str, row: Dict[str, Any], key: Optional[str] = None) -> str:
    """Insert ``row``, or update the existing row with the same key (insert-or-update).

    ``key`` defaults to the sheet's primary key; pass a column name to match on it.
    Returns "inserted" or "updated".
    """
    db = await _attach(sheet_id)
    return await db.upsert({k: str(v) for k, v in row.items()}, key=key)


async def query(sheet_id: str, sql: str) -> List[Dict[str, Any]]:
    """Run a server-side Google Visualization query. Columns are letters (A, B, ...).

    Example: ``SELECT A, B WHERE C = 'pro' ORDER BY A DESC LIMIT 10``.
    """
    db = await _attach(sheet_id)
    return await db.query(sql)


async def share(sheet_id: str, role: Optional[str] = None) -> Dict[str, str]:
    """Make the sheet accessible to anyone with the link; return the shareable URL.

    ``role`` is the public access level: ``"reader"`` (view-only), ``"commenter"``, or
    ``"writer"`` (anyone with the link can EDIT — use with care). "editor" is accepted as
    an alias for "writer". Omit it to use the policy's default; the policy may cap how
    high it can go. Returns the view URL, the CSV-export URL, and the role applied.
    """
    db = await _attach(sheet_id)
    url = await db.share(role=role)
    return {"url": url, "csv_url": db.csv_url, "role": _policy.resolve_share_role(role)}


READ_TOOLS = (columns, read, query)
WRITE_TOOLS = (create_sheet, insert, update, delete, upsert, share)


def build_server(*, read_only: bool = False, policy: Optional[AccessPolicy] = None) -> FastMCP:
    """Build the GSAB MCP server, bound to an AccessPolicy.

    The policy guards every tool (allowed sheets, share-role cap, destructive confirm).
    ``read_only=True`` (or a read-only policy) registers only the read / query tools —
    a safe, look-but-don't-touch mode.
    """
    global _policy
    _policy = policy or AccessPolicy()
    if read_only:
        _policy.read_only = True
    server = FastMCP("gsab")
    for fn in READ_TOOLS:
        server.tool()(fn)
    if not _policy.read_only:
        for fn in WRITE_TOOLS:
            server.tool()(fn)
    return server


# Module-level full server (kept for `from gsab.mcp.server import mcp` and tests).
mcp = build_server()


def main(read_only: bool = False, policy_path: Optional[str] = None) -> None:
    """Run the GSAB MCP server over stdio, optionally under an AccessPolicy profile."""
    policy = AccessPolicy.load(policy_path) if policy_path else None
    build_server(read_only=read_only, policy=policy).run()


if __name__ == "__main__":
    main()
