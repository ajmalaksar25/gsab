"""Server-side querying via the Google Visualization API (gviz).

Pushes filtering, sorting and aggregation to Google's servers using the
Visualization API Query Language (a SQL subset) instead of fetching every row.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import quote

_GVIZ_URL = "https://docs.google.com/spreadsheets/d/{id}/gviz/tq"


def parse_gviz_response(text: str) -> list:
    """Parse the JSONP-wrapped gviz payload into row dicts keyed by column label."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Unexpected gviz response: {text[:120]!r}")
    table = json.loads(text[start : end + 1]).get("table", {})
    cols = [(c.get("label") or c.get("id") or f"c{i}") for i, c in enumerate(table.get("cols", []))]
    rows = []
    for r in table.get("rows", []):
        cells = r.get("c") or []
        rows.append({label: (cell.get("v") if cell else None) for label, cell in zip(cols, cells)})
    return rows


def build_gviz_url(
    spreadsheet_id: str, sql: str, *, sheet: Optional[str] = None, headers: int = 1
) -> str:
    """Build the gviz request URL for a query."""
    params = {"tq": sql, "tqx": "out:json", "headers": str(headers)}
    if sheet:
        params["sheet"] = sheet
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"{_GVIZ_URL.format(id=spreadsheet_id)}?{query}"


def run_gviz_query(
    credentials: Any, spreadsheet_id: str, sql: str, *, sheet: Optional[str] = None
) -> list:
    """Execute a gviz query against a spreadsheet tab and return row dicts."""
    from google.auth.transport.requests import AuthorizedSession

    url = build_gviz_url(spreadsheet_id, sql, sheet=sheet)
    resp = AuthorizedSession(credentials).get(url)
    resp.raise_for_status()
    return parse_gviz_response(resp.text)
