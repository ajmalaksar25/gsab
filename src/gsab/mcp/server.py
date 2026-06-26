"""GSAB MCP server: expose a Google Sheet as a database to an MCP host.

Tools let an agent create a sheet, then insert / read / update / delete / query /
upsert / share it. Columns are treated as text (the agent works with strings); a
created sheet may declare a ``primary_key`` to unlock enforced uniqueness + upsert.

Auth uses the host's GSAB credentials (run ``gsab auth login`` once, or set
``GSAB_SERVICE_ACCOUNT``). Start with ``gsab mcp``.
"""

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ..core.connection import SheetConnection
from ..core.schema import Field, FieldType, Schema
from ..core.sheet_manager import SheetManager
from ..utils.errors import execute

mcp = FastMCP("gsab")

# One SheetManager per spreadsheet id, built lazily from its live header row.
_managers: Dict[str, SheetManager] = {}


async def _attach(sheet_id: str) -> SheetManager:
    """Bind a SheetManager to an existing sheet, inferring text columns from its header."""
    if sheet_id in _managers:
        return _managers[sheet_id]
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
    db = SheetManager(conn, schema)
    db.sheet_id = sheet_id
    _managers[sheet_id] = db
    return db


def _url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


@mcp.tool()
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
    db = SheetManager(SheetConnection(), Schema("data", fields))
    sheet_id = await db.create_sheet(title)
    _managers[sheet_id] = db
    return {"sheet_id": sheet_id, "url": _url(sheet_id)}


@mcp.tool()
async def columns(sheet_id: str) -> List[str]:
    """List the column names (header row) of a sheet."""
    db = await _attach(sheet_id)
    return [f.name for f in db.schema.fields]


@mcp.tool()
async def insert(sheet_id: str, row: Dict[str, Any]) -> str:
    """Insert one row (a dict of column -> value) into the sheet."""
    db = await _attach(sheet_id)
    await db.insert({k: ("" if v is None else str(v)) for k, v in row.items()})
    return "inserted 1 row"


@mcp.tool()
async def read(
    sheet_id: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Read rows as dicts. Optional ``filters`` = {column: value} (equality) or
    {column: {op: value}} with ops $eq $ne $gt $gte $lt $lte $in $nin $contains $regex.
    """
    db = await _attach(sheet_id)
    rows = await db.read(filters)
    return rows[:limit] if limit else rows


@mcp.tool()
async def update(sheet_id: str, filters: Dict[str, Any], changes: Dict[str, Any]) -> str:
    """Update rows matching ``filters``, applying ``changes``. Returns the count changed."""
    db = await _attach(sheet_id)
    n = await db.update(filters, {k: str(v) for k, v in changes.items()})
    return f"updated {n} row(s)"


@mcp.tool()
async def delete(sheet_id: str, filters: Dict[str, Any]) -> str:
    """Delete rows matching ``filters``. Returns the count deleted."""
    db = await _attach(sheet_id)
    n = await db.delete(filters)
    return f"deleted {n} row(s)"


@mcp.tool()
async def upsert(sheet_id: str, row: Dict[str, Any], key: Optional[str] = None) -> str:
    """Insert ``row``, or update the existing row with the same key (insert-or-update).

    ``key`` defaults to the sheet's primary key; pass a column name to match on it.
    Returns "inserted" or "updated".
    """
    db = await _attach(sheet_id)
    return await db.upsert({k: str(v) for k, v in row.items()}, key=key)


@mcp.tool()
async def query(sheet_id: str, sql: str) -> List[Dict[str, Any]]:
    """Run a server-side Google Visualization query. Columns are letters (A, B, ...).

    Example: ``SELECT A, B WHERE C = 'pro' ORDER BY A DESC LIMIT 10``.
    """
    db = await _attach(sheet_id)
    return await db.query(sql)


@mcp.tool()
async def share(sheet_id: str) -> Dict[str, str]:
    """Make the sheet readable by anyone with the link; return the shareable URL."""
    db = await _attach(sheet_id)
    url = await db.share()
    return {"url": url, "csv_url": db.csv_url}


def main() -> None:
    """Run the GSAB MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
