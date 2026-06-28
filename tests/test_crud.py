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

    def append(self, *, spreadsheetId, range, valueInputOption, body):
        self.conn.appended.append(body["values"])
        return _Request({})


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
    def __init__(self, grid, *, col_a=None, batch_reply=None, tab="t", sheet_id=7, connected=True):
        self.grid = grid
        self.col_a = col_a or [[r[0]] for r in grid]
        self.metadata = {"sheets": [{"properties": {"title": tab, "sheetId": sheet_id}}]}
        self.batch_reply = batch_reply or {}
        self.batched = []
        self.appended = []
        self.credentials = None
        self.service = _Service(self)
        self.connected = connected
        self.connect_calls = 0

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True
        self.connect_calls += 1


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


async def test_read_connects_lazily_when_attached_to_existing_sheet():
    # Attaching to an existing sheet (set sheet_id, no create_sheet) must still
    # connect on first use — multi-connection / existing-sheet pattern.
    conn = FakeConnection([["id", "age"], ["1", "20"]], connected=False)
    db = SheetManager(conn, _schema())
    db.sheet_id = "SHEET"
    rows = await db.read()
    assert conn.connect_calls == 1
    assert rows == [{"id": 1, "age": 20}]


async def test_read_strips_internal_row_index():
    grid = [["id", "age"], ["1", "20"], ["2", "30"]]
    db = SheetManager(FakeConnection(grid), _schema())
    db.sheet_id = "SHEET"
    rows = await db.read()
    assert rows == [{"id": 1, "age": 20}, {"id": 2, "age": 30}]  # clean, schema-typed
    assert all("_row_index" not in r for r in rows)


def _pk_schema():
    return Schema(
        "t",
        [
            Field("id", FieldType.INTEGER, primary_key=True),
            Field("age", FieldType.INTEGER, required=True),
        ],
    )


async def test_primary_key_implies_required_and_unique():
    schema = _pk_schema()
    pk = schema.get_field("id")
    assert pk.required and pk.unique
    assert schema.primary_key == "id"
    assert [f.name for f in schema.unique_fields] == ["id"]


def test_schema_rejects_two_primary_keys():
    with pytest.raises(ValueError) as exc:
        Schema(
            "t",
            [
                Field("a", FieldType.INTEGER, primary_key=True),
                Field("b", FieldType.INTEGER, primary_key=True),
            ],
        )
    assert "at most one primary_key" in str(exc.value)


async def test_insert_rejects_duplicate_primary_key():
    from gsab.exceptions.custom_exceptions import DuplicateKeyError

    conn = FakeConnection([["id", "age"], ["1", "20"]])
    db = SheetManager(conn, _pk_schema())
    db.sheet_id = "SHEET"
    with pytest.raises(DuplicateKeyError) as exc:
        await db.insert({"id": 1, "age": 99})
    assert "id" in str(exc.value)
    assert conn.appended == []  # nothing written


async def test_bulk_insert_rejects_within_batch_duplicate():
    from gsab.exceptions.custom_exceptions import DuplicateKeyError

    conn = FakeConnection([["id", "age"]])  # empty (header only)
    db = SheetManager(conn, _pk_schema())
    db.sheet_id = "SHEET"
    with pytest.raises(DuplicateKeyError):
        await db.bulk_insert([{"id": 5, "age": 10}, {"id": 5, "age": 20}])
    assert conn.appended == []


async def test_insert_allows_new_key():
    conn = FakeConnection([["id", "age"], ["1", "20"]])
    db = SheetManager(conn, _pk_schema())
    db.sheet_id = "SHEET"
    await db.insert({"id": 2, "age": 30})
    assert conn.appended == [[[2, 30]]]  # typed cells, single append


async def test_upsert_inserts_when_key_absent():
    conn = FakeConnection([["id", "age"], ["1", "20"]])
    db = SheetManager(conn, _pk_schema())
    db.sheet_id = "SHEET"
    status = await db.upsert({"id": 9, "age": 40})
    assert status == "inserted"
    assert conn.appended == [[[9, 40]]]
    assert conn.batched == []  # no update path


async def test_upsert_updates_existing_row_and_merges():
    conn = FakeConnection([["id", "age"], ["1", "20"], ["2", "30"]])
    db = SheetManager(conn, _pk_schema())
    db.sheet_id = "SHEET"
    status = await db.upsert({"id": 2, "age": 99})
    assert status == "updated"
    assert conn.appended == []  # nothing inserted
    req = conn.batched[0]["requests"][0]["updateCells"]
    assert (req["range"]["startRowIndex"], req["range"]["endRowIndex"]) == (2, 3)  # id=2 row
    written = [c["userEnteredValue"] for c in req["rows"][0]["values"]]
    assert written == [{"numberValue": 2}, {"numberValue": 99}]


async def test_bulk_upsert_counts_and_last_write_wins():
    conn = FakeConnection([["id", "age"], ["1", "20"]])
    db = SheetManager(conn, _pk_schema())
    db.sheet_id = "SHEET"
    # id=1 exists (update); id=7 twice in batch (insert once, last wins).
    result = await db.bulk_upsert(
        [{"id": 1, "age": 21}, {"id": 7, "age": 70}, {"id": 7, "age": 77}]
    )
    assert result == {"inserted": 1, "updated": 1}
    assert conn.appended == [[[7, 77]]]  # last value wins, one row


async def test_upsert_without_key_raises():
    conn = FakeConnection([["id", "age"], ["1", "20"]])
    db = SheetManager(conn, _schema())  # no primary key
    db.sheet_id = "SHEET"
    with pytest.raises(Exception) as exc:
        await db.upsert({"id": 1, "age": 5})
    assert "key" in str(exc.value).lower()


def test_field_constraints_are_enforced_on_write():
    from gsab.core.schema import ValidationRule

    s = Schema(
        "t",
        [
            Field("id", FieldType.INTEGER, primary_key=True),
            Field("age", FieldType.INTEGER, min_value=0, max_value=150),
            Field("score", FieldType.INTEGER, min_value=0),  # not named "age"
            Field("name", FieldType.STRING, min_length=2, max_length=5),
            Field("email", FieldType.STRING, pattern=r"[^@]+@[^@]+\.[^@]+"),
            Field(
                "rank",
                FieldType.INTEGER,
                validation_rules=[ValidationRule(lambda x: x % 2 == 0, "rank must be even")],
            ),
        ],
    )
    ok = {"id": 1, "age": 30, "score": 1, "name": "ok", "email": "a@b.io", "rank": 2}
    assert s.validate(ok) == []
    assert s.validate({**ok, "age": 200})  # max_value enforced
    assert s.validate({**ok, "score": -5})  # min_value enforced on a non-"age" field
    assert s.validate({**ok, "name": "toolong"})  # max_length enforced
    assert s.validate({**ok, "name": "x"})  # min_length enforced
    assert s.validate({**ok, "email": "nope"})  # pattern enforced
    assert s.validate({**ok, "rank": 3})  # custom rule enforced
    assert s.validate({**ok, "age": True})  # bool rejected for INTEGER


def test_field_with_default_is_optional():
    schema = Schema(
        "t",
        [
            Field("id", FieldType.INTEGER, primary_key=True),
            Field("plan", FieldType.STRING, default="free"),  # required defaults True
        ],
    )
    # Omitting a field that has a default is fine; omitting a plain required field is not.
    assert schema.validate({"id": 1}) == []
    assert schema.validate({"plan": "pro"}) == ["Field id is required"]


async def test_insert_applies_default_when_field_omitted():
    schema = Schema(
        "t",
        [
            Field("id", FieldType.INTEGER, primary_key=True),
            Field("plan", FieldType.STRING, default="free"),
        ],
    )
    conn = FakeConnection([["id", "plan"]])
    db = SheetManager(conn, schema)
    db.sheet_id = "SHEET"
    await db.insert({"id": 1})  # plan omitted -> default
    assert conn.appended == [[[1, "free"]]]


async def test_upsert_on_explicit_key_field():
    # No PK declared, but match on an explicit key column.
    conn = FakeConnection([["id", "age"], ["1", "20"]])
    db = SheetManager(conn, _schema())
    db.sheet_id = "SHEET"
    status = await db.upsert({"id": 1, "age": 50}, key="id")
    assert status == "updated"


async def test_json_field_round_trips_through_object():
    schema = Schema(
        "t",
        [
            Field("id", FieldType.INTEGER, primary_key=True),
            Field("meta", FieldType.JSON),
        ],
    )
    conn = FakeConnection([["id", "meta"]])
    db = SheetManager(conn, schema)
    db.sheet_id = "SHEET"
    await db.insert({"id": 1, "meta": {"a": 1, "b": [2, 3]}})
    stored = conn.appended[0][0][1]
    assert stored == '{"a": 1, "b": [2, 3]}'  # serialized JSON string at rest
    # Read it back — the stored string is parsed back into the original object.
    conn.grid = [["id", "meta"], ["1", stored]]
    conn.col_a = [["id"], ["1"]]
    rows = await db.read()
    assert rows == [{"id": 1, "meta": {"a": 1, "b": [2, 3]}}]


async def test_encryption_round_trips_through_sheet_manager():
    from cryptography.fernet import Fernet

    from gsab.utils.encryption import Encryptor

    key = Fernet.generate_key().decode()
    schema = Schema(
        "t",
        [
            Field("id", FieldType.INTEGER, primary_key=True),
            Field("secret", FieldType.STRING, encrypted=True),
        ],
    )
    conn = FakeConnection([["id", "secret"]])
    db = SheetManager(conn, schema, encryption_key=key)
    db.sheet_id = "SHEET"
    await db.insert({"id": 1, "secret": "hunter2"})
    stored = conn.appended[0][0][1]
    assert stored != "hunter2"  # encrypted at rest, not plaintext
    assert Encryptor(key).decrypt(stored) == "hunter2"
    # read() decrypts transparently.
    conn.grid = [["id", "secret"], ["1", stored]]
    conn.col_a = [["id"], ["1"]]
    rows = await db.read()
    assert rows == [{"id": 1, "secret": "hunter2"}]


async def test_upsert_race_window_both_insert_on_stale_read():
    # Pins the DOCUMENTED read-check-write race: two upserts that read the same
    # pre-insert state both append, because Sheets has no conditional write. Not
    # desired behaviour — this guards against ever implying upsert is atomic.
    conn = FakeConnection([["id", "age"]])  # the fake grid does not grow on append
    db = SheetManager(conn, _pk_schema())
    db.sheet_id = "SHEET"
    assert await db.upsert({"id": 1, "age": 10}) == "inserted"
    assert await db.upsert({"id": 1, "age": 20}) == "inserted"  # stale read → also inserts
    assert len(conn.appended) == 2


def test_csv_url_points_at_export_endpoint():
    db = SheetManager(FakeConnection([["id", "age"]]), _schema())
    db.sheet_id = "SHEET123"
    assert db.csv_url == "https://docs.google.com/spreadsheets/d/SHEET123/export?format=csv"


async def test_share_rejects_bad_role():
    db = SheetManager(FakeConnection([["id", "age"]]), _schema())
    db.sheet_id = "SHEET"
    with pytest.raises(Exception) as exc:
        await db.share(role="owner")
    assert "reader" in str(exc.value)


async def test_share_and_unshare_drive_permissions(monkeypatch):
    calls = {}

    class _FakeDrive:
        def permissions(self):
            return self

        def files(self):
            return self

        def create(self, *, fileId, body, fields):
            calls["create"] = body
            return _Request({"id": "anyoneWithLink"})

        def get(self, *, fileId, fields):
            return _Request({"webViewLink": "https://docs.google.com/spreadsheets/d/SHEET/edit"})

        def delete(self, *, fileId, permissionId):
            calls["delete"] = permissionId
            return _Request({})

    db = SheetManager(FakeConnection([["id", "age"]]), _schema())
    db.sheet_id = "SHEET"
    monkeypatch.setattr(db, "_drive", lambda: _FakeDrive())

    url = await db.share()
    assert calls["create"] == {"type": "anyone", "role": "reader"}
    assert url == "https://docs.google.com/spreadsheets/d/SHEET/edit"

    await db.unshare()
    assert calls["delete"] == "anyoneWithLink"


async def test_share_role_alias_and_commenter(monkeypatch):
    # "editor" is a friendly alias for the API role "writer"; "commenter" is accepted.
    bodies = []

    class _FakeDrive:
        def permissions(self):
            return self

        def files(self):
            return self

        def create(self, *, fileId, body, fields):
            bodies.append(body)
            return _Request({"id": "anyoneWithLink"})

        def get(self, *, fileId, fields):
            return _Request({"webViewLink": "https://docs.google.com/spreadsheets/d/SHEET/edit"})

    db = SheetManager(FakeConnection([["id", "age"]]), _schema())
    db.sheet_id = "SHEET"
    monkeypatch.setattr(db, "_drive", lambda: _FakeDrive())

    await db.share(role="editor")
    await db.share(role="commenter")
    assert [b["role"] for b in bodies] == ["writer", "commenter"]


async def test_policy_read_only_blocks_writes():
    from gsab import AccessPolicy
    from gsab.exceptions import PolicyError

    db = SheetManager(
        FakeConnection([["id", "age"]]), _schema(), policy=AccessPolicy(read_only=True)
    )
    db.sheet_id = "S"
    with pytest.raises(PolicyError):
        await db.insert({"id": 1, "age": 20})


async def test_policy_allowlist_blocks_foreign_sheet_but_allows_listed():
    from gsab import AccessPolicy
    from gsab.exceptions import PolicyError

    db = SheetManager(
        FakeConnection([["id", "age"], ["1", "20"]]),
        _schema(),
        policy=AccessPolicy(allowed_sheets=["OK"]),
    )
    db.sheet_id = "FORBIDDEN"
    with pytest.raises(PolicyError):
        await db.read()
    db.sheet_id = "OK"
    assert len(await db.read()) == 1


async def test_policy_created_sheet_is_allowlist_exempt():
    from gsab import AccessPolicy

    db = SheetManager(
        FakeConnection([["id", "age"], ["1", "20"]]),
        _schema(),
        policy=AccessPolicy(allowed_sheets=["OTHER"]),
    )
    db.sheet_id = "NEW"
    db._created_here = True  # as create_sheet() would set it
    assert len(await db.read()) == 1


async def test_policy_on_activity_receives_events():
    from gsab import AccessPolicy

    events = []
    db = SheetManager(
        FakeConnection([["id", "age"], ["1", "20"]]),
        _schema(),
        policy=AccessPolicy(on_activity=events.append),
    )
    db.sheet_id = "S"
    await db.read()
    assert any(e["op"] == "read" and e["count"] == 1 for e in events)


async def test_policy_confirm_destructive_gates_delete():
    from gsab import AccessPolicy
    from gsab.exceptions import PolicyError

    db = SheetManager(
        FakeConnection([["id", "age"], ["1", "20"]]),
        _schema(),
        policy=AccessPolicy(confirm_destructive=True),
    )
    db.sheet_id = "S"
    with pytest.raises(PolicyError):
        await db.delete({"id": 1})
    assert await db.delete({"id": 1}, confirm=True) == 1


async def test_watch_emits_initial_snapshot_then_diffs():
    conn = FakeConnection([["id", "age"], ["1", "20"], ["2", "30"]])
    db = SheetManager(conn, _pk_schema())
    db.sheet_id = "SHEET"
    w = db.watch(interval=0.001)

    initial = await w.__anext__()
    assert initial == {
        "added": [{"id": 1, "age": 20}, {"id": 2, "age": 30}],
        "updated": [],
        "removed": [],
    }

    conn.grid = [["id", "age"], ["1", "20"], ["2", "30"], ["3", "40"]]  # add id=3
    assert await w.__anext__() == {"added": [{"id": 3, "age": 40}], "updated": [], "removed": []}

    conn.grid = [["id", "age"], ["1", "21"], ["2", "30"], ["3", "40"]]  # update id=1
    assert await w.__anext__() == {"added": [], "updated": [{"id": 1, "age": 21}], "removed": []}

    conn.grid = [["id", "age"], ["1", "21"], ["3", "40"]]  # remove id=2
    assert await w.__anext__() == {"added": [], "updated": [], "removed": [{"id": 2, "age": 30}]}

    await w.aclose()


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
