"""Offline tests that CRUD ops build the right Google API requests.

A fake Sheets service captures request bodies so we can assert the wire shape
without touching a live spreadsheet — notably the `delete()` row-index fix (#15)
and native chart spec (#14).
"""

import pytest

from gsab.core.schema import Field, FieldType, Schema
from gsab.core.sheet_manager import SheetManager


class _Request:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _Values:
    def __init__(self, conn):
        self.conn = conn

    def get(self, *, spreadsheetId, range):
        # column-only range (e.g. "t!A:A") is the chart extent probe
        rows = self.conn.col_a if range.endswith("!A:A") else self.conn.grid
        return _Request({"values": rows})


class _Spreadsheets:
    def __init__(self, conn):
        self.conn = conn

    def values(self):
        return _Values(self.conn)

    def get(self, *, spreadsheetId):
        return _Request(self.conn.metadata)

    def batchUpdate(self, *, spreadsheetId, body):
        self.conn.batched.append(body)
        return _Request(self.conn.batch_reply)


class _Service:
    def __init__(self, conn):
        self.conn = conn

    def spreadsheets(self):
        return _Spreadsheets(self.conn)


class FakeConnection:
    def __init__(self, grid, *, col_a=None, batch_reply=None, tab="t", sheet_id=7):
        self.grid = grid
        self.col_a = col_a or [[r[0]] for r in grid]
        self.metadata = {"sheets": [{"properties": {"title": tab, "sheetId": sheet_id}}]}
        self.batch_reply = batch_reply or {}
        self.batched = []
        self.credentials = None
        self.service = _Service(self)

    def is_connected(self):
        return True

    async def connect(self):
        return None


def _schema():
    return Schema(
        "t",
        [
            Field("id", FieldType.INTEGER, required=True),
            Field("age", FieldType.INTEGER, required=True),
        ],
    )


async def test_delete_uses_true_row_index_with_duplicates():
    # Two identical (id=2, age=30) rows — the old `all_rows.index(row)` lookup
    # would have resolved both to the same (first) index. _row_index must not.
    grid = [
        ["id", "age"],
        ["1", "20"],
        ["2", "30"],
        ["2", "30"],
        ["3", "40"],
    ]
    conn = FakeConnection(grid)
    db = SheetManager(conn, _schema())
    db.sheet_id = "SHEET"

    deleted = await db.delete({"id": 2})

    assert deleted == 2
    assert len(conn.batched) == 1  # single batched call
    ranges = [r["deleteDimension"]["range"] for r in conn.batched[0]["requests"]]
    # rows at 0-based sheet indices 2 and 3, highest first so indices stay valid
    assert [(r["startIndex"], r["endIndex"]) for r in ranges] == [(3, 4), (2, 3)]
    assert all(r["sheetId"] == 7 for r in ranges)


async def test_delete_no_match_makes_no_calls():
    conn = FakeConnection([["id", "age"], ["1", "20"]])
    db = SheetManager(conn, _schema())
    db.sheet_id = "SHEET"
    assert await db.delete({"id": 99}) == 0
    assert conn.batched == []


async def test_chart_builds_basic_chart_spec():
    grid = [["id", "age"], ["1", "20"], ["2", "30"], ["3", "40"]]
    reply = {"replies": [{"addChart": {"chart": {"chartId": 123}}}]}
    conn = FakeConnection(grid, batch_reply=reply)
    db = SheetManager(conn, _schema())
    db.sheet_id = "SHEET"

    chart_id = await db.chart(x="id", y="age", kind="line", title="Ages")

    assert chart_id == 123
    spec = conn.batched[0]["requests"][0]["addChart"]["chart"]["spec"]
    assert spec["title"] == "Ages"
    basic = spec["basicChart"]
    assert basic["chartType"] == "LINE"
    dom = basic["domains"][0]["domain"]["sourceRange"]["sources"][0]
    ser = basic["series"][0]["series"]["sourceRange"]["sources"][0]
    assert (dom["startColumnIndex"], dom["endColumnIndex"]) == (0, 1)  # id -> col A
    assert (ser["startColumnIndex"], ser["endColumnIndex"]) == (1, 2)  # age -> col B
    assert dom["endRowIndex"] == 4  # header + 3 data rows


async def test_chart_rejects_unknown_field():
    conn = FakeConnection([["id", "age"], ["1", "20"]])
    db = SheetManager(conn, _schema())
    db.sheet_id = "SHEET"
    with pytest.raises(Exception) as exc:
        await db.chart(x="id", y="nope")
    assert "nope" in str(exc.value)


async def test_op_before_sheet_bound_raises():
    db = SheetManager(FakeConnection([["id", "age"]]), _schema())
    with pytest.raises(Exception):
        await db.read()


async def test_read_strips_internal_row_index():
    grid = [["id", "age"], ["1", "20"], ["2", "30"]]
    db = SheetManager(FakeConnection(grid), _schema())
    db.sheet_id = "SHEET"
    rows = await db.read()
    assert rows == [{"id": 1, "age": 20}, {"id": 2, "age": 30}]  # clean, schema-typed
    assert all("_row_index" not in r for r in rows)


async def test_query_coerces_field_columns_to_schema_types(monkeypatch):
    # gviz returns numbers as floats; query() coerces columns that map to a schema
    # field back to its declared type (id/age -> int), leaving aggregate labels alone.
    raw = [{"id": 1.0, "age": 20.0, "avg age": 25.0}]
    monkeypatch.setattr("gsab.core.query.run_gviz_query", lambda *a, **k: raw)
    db = SheetManager(FakeConnection([["id", "age"]]), _schema())
    db.sheet_id = "SHEET"
    out = await db.query("SELECT A, B, AVG(B)")
    assert isinstance(out[0]["id"], int) and out[0]["id"] == 1
    assert isinstance(out[0]["age"], int) and out[0]["age"] == 20
    assert out[0]["avg age"] == 25.0  # unknown label stays gviz-native
