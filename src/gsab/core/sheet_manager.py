import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from googleapiclient.discovery import build

from ..exceptions.custom_exceptions import DuplicateKeyError, NotFoundError, ValidationError
from ..utils.encryption import Encryptor
from ..utils.errors import execute
from .connection import SheetConnection
from .schema import FieldType, Schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_OPERATORS = (
    "$eq",
    "$ne",
    "$gt",
    "$gte",
    "$lt",
    "$lte",
    "$in",
    "$nin",
    "$contains",
    "$regex",
)

# Google chart types: `basicChart` covers most; PIE uses its own spec.
_BASIC_CHARTS = frozenset({"COLUMN", "BAR", "LINE", "AREA", "SCATTER", "COMBO", "STEPPED_AREA"})
_CHART_TYPES = _BASIC_CHARTS | {"PIE"}


def _match_op(actual: Any, op: str, target: Any) -> bool:
    """Evaluate a single filter operator against a record value."""
    try:
        if op == "$eq":
            return actual == target
        if op == "$ne":
            return actual != target
        if op == "$gt":
            return actual is not None and actual > target
        if op == "$gte":
            return actual is not None and actual >= target
        if op == "$lt":
            return actual is not None and actual < target
        if op == "$lte":
            return actual is not None and actual <= target
        if op == "$in":
            return actual in target
        if op == "$nin":
            return actual not in target
        if op == "$contains":
            return str(target) in str(actual)
        if op == "$regex":
            return re.search(target, str(actual)) is not None
    except TypeError:
        return False
    raise ValidationError(f"Unknown filter operator: {op}. Use one of: {', '.join(_OPERATORS)}.")


class SheetManager:
    """Async CRUD over one Google Sheet tab, driven by a `Schema`.

    Binds a `SheetConnection` to a `Schema` (one tab = one table) and exposes
    create / insert / read / update / delete / `upsert()`, server-side `query()`,
    the pandas bridge (`to_dataframe()` / `from_dataframe()`) and native `chart()`.
    Validation runs on every write; fields flagged `encrypted=True` are sealed
    before they reach the sheet and decrypted on read. A `unique`/`primary_key`
    field is enforced on insert/upsert (read-check-write; `DuplicateKeyError`).

    Args:
        connection: a `SheetConnection` (connected lazily on first use).
        schema: the `Schema` describing the tab.
        encryption_key: Fernet key; required only if the schema has encrypted fields.

    Example:
        db = SheetManager(connection, schema, encryption_key=key)
        await db.create_sheet("My App DB")
        await db.insert({"id": 1, "name": "Ada"})
        rows = await db.read({"id": {"$gte": 1}})

    Every method raises a subclass of `GSABError` on failure — `ValidationError`
    for bad input, `NotFoundError` for a missing sheet, `QuotaExceededError` when
    rate-limited. Transient errors (429/5xx, dropped connections) are retried
    automatically with backoff.
    """

    def __init__(
        self, connection: SheetConnection, schema: Schema, encryption_key: Optional[str] = None
    ):
        """Initialize sheet manager."""
        self.connection = connection
        self.schema = schema
        self.sheet_id = None
        self._field_map = {field.name: field for field in self.schema.fields}

        # Initialize encryptor only if we have encrypted fields
        has_encrypted_fields = any(field.encrypted for field in self.schema.fields)
        self.encryptor = (
            Encryptor(encryption_key) if has_encrypted_fields and encryption_key else None
        )

    def _require_sheet(self) -> None:
        """Ensure a spreadsheet is bound before an operation runs."""
        if not self.sheet_id:
            raise ValidationError(
                "No spreadsheet bound. Call `await db.create_sheet(title)` first, "
                "or set `db.sheet_id` to an existing spreadsheet id."
            )

    async def _ensure_connected(self) -> None:
        if not self.connection.is_connected():
            await self.connection.connect()

    async def create_sheet(self, title: str) -> str:
        """
        Create a new sheet with the defined schema.

        Args:
            title: Name of the sheet

        Returns:
            Sheet ID
        """
        await self._ensure_connected()
        spreadsheet = {
            "properties": {"title": title},
            "sheets": [
                {
                    "properties": {"title": self.schema.name},
                    "data": [{"rowData": {"values": self._create_header_row()}}],
                }
            ],
        }
        result = await execute(
            self.connection.service.spreadsheets().create(body=spreadsheet), op="create_sheet"
        )
        self.sheet_id = result["spreadsheetId"]
        logger.info("Created new sheet with ID: %s", self.sheet_id)
        return self.sheet_id

    def _cell(self, field, value: Any) -> Any:
        """Typed cell value for one field — encrypts flagged fields, keeps native types.

        Numbers and booleans are written as their JSON types so Google stores them
        as real numbers (enabling server-side numeric queries via ``query()``).
        Strings stay strings under ``RAW`` input, so a leading ``=`` is inert text,
        never an executable formula. Dates are stored as ISO text.
        """
        if value is None:
            value = field.default
        if value is None or value == "":
            return ""
        value = self.schema._convert_value(value, field.field_type)
        if field.field_type == FieldType.JSON:
            # Store JSON as a serialized string (so it round-trips back to an object).
            value = json.dumps(value, default=str)
        if field.encrypted and self.encryptor:
            return self.encryptor.encrypt(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value

    def _encode_row(self, data: Dict[str, Any]) -> List[Any]:
        """Validate one record and return its typed cell values."""
        errors = self.schema.validate(data)
        if errors:
            raise ValidationError(f"Validation errors: {', '.join(errors)}")
        return [self._cell(field, data.get(field.name)) for field in self.schema.fields]

    def _user_entered(self, field, value: Any) -> Dict[str, Any]:
        """Build a typed Sheets ``userEnteredValue`` for the update path."""
        cell = self._cell(field, value)
        if isinstance(cell, bool):
            return {"boolValue": cell}
        if isinstance(cell, (int, float)):
            return {"numberValue": cell}
        return {"stringValue": str(cell)}

    def _decode_value(self, field, value: Any) -> Any:
        """Decrypt (if flagged) and convert a raw cell to the field's Python type."""
        if field.encrypted and self.encryptor and value:
            try:
                value = self.encryptor.decrypt(value)
            except Exception as e:
                logger.warning("Failed to decrypt field %s: %s", field.name, e)
        try:
            return self.schema._convert_value(value, field.field_type)
        except ValueError:
            return str(value)

    async def insert(self, data: Dict[str, Any]) -> None:
        """Insert a single record.

        Args:
            data: field name -> value; validated against the schema first.
                Missing optional fields use their ``default`` (or an empty cell).

        Raises:
            ValidationError: the record fails schema validation, or no sheet is bound.
            GSABError: on an API failure (e.g. NotFoundError, QuotaExceededError).
        """
        await self.bulk_insert([data])

    async def bulk_insert(self, records: List[Dict[str, Any]]) -> int:
        """Insert many records in a single append call. Returns the number inserted.

        If the schema declares any `unique` / `primary_key` field, the batch is
        checked against the existing rows (and itself) first and a clashing key
        raises `DuplicateKeyError` — use `upsert()` to insert-or-update instead.
        That check is a read-check-write, so two concurrent inserts of the same new
        key can still both land; schemas with no unique field skip the read entirely.
        """
        self._require_sheet()
        await self._ensure_connected()
        rows = [self._encode_row(r) for r in records]
        if not rows:
            return 0
        await self._check_unique(records)
        await self._append_rows(rows)
        logger.info("Inserted %d row(s)", len(rows))
        return len(rows)

    async def _append_rows(self, rows: List[List[Any]]) -> None:
        """Append already-encoded rows to the tab (no validation or uniqueness check)."""
        await execute(
            self.connection.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.sheet_id,
                range=f"{self.schema.name}!A:A",
                valueInputOption="RAW",
                body={"values": rows},
            ),
            op="insert",
        )

    async def _check_unique(self, records: List[Dict[str, Any]]) -> None:
        """Reject a batch that would duplicate any `unique`/`primary_key` field.

        Compares incoming values (in their schema type) against the values already
        in the sheet and against earlier records in the same batch. No-ops when the
        schema has no unique field, so the common insert path stays read-free.
        """
        if not self.schema.unique_fields:
            return
        existing = await self._read_indexed()
        for field in self.schema.unique_fields:
            seen = {r.get(field.name) for r in existing if r.get(field.name) not in (None, "")}
            for record in records:
                value = record.get(field.name)
                if value in (None, ""):
                    continue
                typed = self.schema._convert_value(value, field.field_type)
                if typed in seen:
                    raise DuplicateKeyError(
                        f"Duplicate value for unique field '{field.name}': {typed!r} "
                        f"already exists. Use upsert() to insert-or-update, or change it."
                    )
                seen.add(typed)

    async def from_dataframe(self, df) -> int:
        """Insert every row of a pandas DataFrame in bulk. Returns the number inserted."""
        return await self.bulk_insert(df.to_dict("records"))

    async def to_dataframe(self, filters: Optional[Dict[str, Any]] = None):
        """Read records into a pandas DataFrame (install the `pandas` extra)."""
        import pandas as pd

        return pd.DataFrame(await self.read(filters))

    def _create_header_row(self) -> List[Dict]:
        """
        Create header row based on schema fields.

        Returns:
            List of cell values for the header row
        """
        return [
            {
                "userEnteredValue": {"stringValue": field.name},
                "userEnteredFormat": {
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    "textFormat": {"bold": True},
                    "horizontalAlignment": "CENTER",
                },
            }
            for field in self.schema.fields
        ]

    async def read(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Read records matching the filters, as dicts keyed by field name.

        Filtering happens in Python (every row is fetched). For server-side
        filtering/sorting/aggregation use `query()` instead.

        Args:
            filters: optional ``{field: value}`` (equality) or ``{field: {op: value}}``.
                Operators: ``$eq $ne $gt $gte $lt $lte $in $nin $contains $regex``.
                Omit to read every row.

        Returns:
            A list of dicts, one per matching row, with values in their schema
            types (encrypted fields are decrypted).

        Raises:
            ValidationError: no sheet is bound (call `create_sheet()` first).
            GSABError: on an API failure (NotFoundError, PermissionDeniedError, …).
        """
        records = await self._read_indexed(filters)
        for record in records:
            record.pop("_row_index", None)
        return records

    async def _read_indexed(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Like :meth:`read`, but each record carries ``_row_index`` (its 0-based sheet
        row) for the update/delete machinery. Internal — public ``read`` strips it."""
        self._require_sheet()
        await self._ensure_connected()
        result = await execute(
            self.connection.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.sheet_id, range=f"{self.schema.name}!A:Z"),
            op="read",
        )

        values = result.get("values")
        if not values or len(values) <= 1:  # Missing or header-only
            return []

        headers = values[0]
        records = []
        for row_index, row in enumerate(values[1:], start=1):
            record = {}

            # Pad row with empty strings if necessary
            row_data = row + [""] * (len(headers) - len(row))

            for header, value in zip(headers, row_data):
                field = self._field_map.get(header)
                if field:
                    record[header] = self._decode_value(field, value)

            # 0-based sheet row index (header is row 0) — used by update/delete.
            record["_row_index"] = row_index

            if filters and not self._matches_filters(record, filters):
                continue

            records.append(record)

        return records

    def _matches_filters(self, record: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check whether a record matches all filters (equality or operator dicts).

        Operators: $eq $ne $gt $gte $lt $lte $in $nin $contains $regex.
        """
        for field, cond in filters.items():
            actual = record.get(field)
            if isinstance(cond, dict):
                if not all(_match_op(actual, op, target) for op, target in cond.items()):
                    return False
            elif actual != cond:
                return False
        return True

    def column(self, field_name: str) -> str:
        """Return the spreadsheet column letter (A, B, …) for a schema field."""
        names = [f.name for f in self.schema.fields]
        if field_name not in names:
            raise ValidationError(f"Unknown field: {field_name}. Fields: {', '.join(names)}.")
        return chr(ord("A") + names.index(field_name))

    async def query(self, sql: str) -> List[Dict[str, Any]]:
        """Run a Google Visualization (gviz) query against this tab, server-side.

        Columns are referenced by letter — use ``column()`` to map a field name.
        Example::

            await db.query("SELECT A, D WHERE D = 'pro' ORDER BY A DESC LIMIT 10")

        Returns a list of dicts keyed by the sheet's header labels. Columns that
        map to a schema field come back in that field's Python type (and decrypted),
        matching ``read()``; aggregates like ``SUM(D)`` stay gviz-native. Filtering,
        sorting and aggregation run on Google's servers, not in Python.
        """
        self._require_sheet()
        await self._ensure_connected()
        from .query import run_gviz_query

        rows = run_gviz_query(
            self.connection.credentials, self.sheet_id, sql, sheet=self.schema.name
        )
        for row in rows:
            for key, value in row.items():
                field = self._field_map.get(key)
                if field is not None and value is not None:
                    row[key] = self._decode_value(field, value)
        return rows

    async def _tab_id(self) -> int:
        """Return this tab's numeric ``sheetId`` (not the spreadsheet id)."""
        meta = await execute(
            self.connection.service.spreadsheets().get(spreadsheetId=self.sheet_id),
            op="metadata",
        )
        for sheet in meta["sheets"]:
            if sheet["properties"]["title"] == self.schema.name:
                return sheet["properties"]["sheetId"]
        raise NotFoundError(f"Tab '{self.schema.name}' not found in spreadsheet {self.sheet_id}.")

    def _update_cells_request(
        self, sheet_id: int, row_index: int, record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a single ``updateCells`` request writing ``record`` to one sheet row.

        ``record`` is the full row (all field names → values); callers merge their
        changes over the existing values first. ``row_index`` is 0-based (header = 0).
        """
        values = [self._user_entered(field, record.get(field.name)) for field in self.schema.fields]
        return {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(self.schema.fields),
                },
                "rows": [{"values": [{"userEnteredValue": v} for v in values]}],
                "fields": "userEnteredValue",
            }
        }

    @staticmethod
    def _merge(record: Dict[str, Any], changes: Dict[str, Any]) -> Dict[str, Any]:
        """Overlay ``changes`` on an existing record, dropping the internal row index."""
        merged = {k: v for k, v in record.items() if k != "_row_index"}
        merged.update(changes)
        return merged

    async def update(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """Update records matching the filters. Returns the number of rows updated."""
        self._require_sheet()
        matching_records = await self._read_indexed(filters)
        if not matching_records:
            logger.info("No rows found matching the filters")
            return 0

        sheet_id = await self._tab_id()
        requests = [
            self._update_cells_request(sheet_id, record["_row_index"], self._merge(record, updates))
            for record in matching_records
        ]
        await execute(
            self.connection.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id, body={"requests": requests}
            ),
            op="update",
        )
        return len(matching_records)

    async def upsert(self, data: Dict[str, Any], *, key: Optional[str] = None) -> str:
        """Insert ``data``, or update the existing row with the same key.

        The key defaults to the schema's `primary_key`; pass ``key="field"`` to match
        on another field instead. On a match the row is updated (fields you omit keep
        their current value); otherwise the record is inserted.

        Args:
            data: the record to insert or merge in; must include the key field.
            key: field to match on (defaults to the schema's primary key).

        Returns:
            ``"inserted"`` or ``"updated"``.

        Raises:
            ValidationError: no key is available, or ``data`` omits the key value.

        Note:
            This is a read-check-write — Google Sheets has no conditional write — so
            two concurrent upserts of the same new key can both insert (duplicate), and
            concurrent updates are last-write-wins.
        """
        result = await self.bulk_upsert([data], key=key)
        return "updated" if result["updated"] else "inserted"

    async def bulk_upsert(
        self, records: List[Dict[str, Any]], *, key: Optional[str] = None
    ) -> Dict[str, int]:
        """Insert-or-update many records keyed on ``key`` (default: the primary key).

        Reads the tab once, then appends the new rows and updates the matching ones —
        at most one append plus one batched update. Within ``records``, the last entry
        for a given key wins. Returns ``{"inserted": n, "updated": m}`` (row counts).
        See `upsert()` for the race-window caveat.
        """
        self._require_sheet()
        key = key or self.schema.primary_key
        if not key:
            raise ValidationError(
                "upsert needs a key. Declare one with Field(..., primary_key=True), "
                "or pass key='<field>' to match on a specific field."
            )
        if key not in self._field_map:
            raise ValidationError(
                f"Unknown key field '{key}'. Fields: {', '.join(self._field_map)}."
            )

        field = self._field_map[key]
        # Last-write-wins within the batch; key the dict by the typed key value.
        deduped: Dict[Any, Dict[str, Any]] = {}
        for record in records:
            value = record.get(key)
            if value in (None, ""):
                raise ValidationError(f"upsert requires a value for key field '{key}'.")
            deduped[self.schema._convert_value(value, field.field_type)] = record
        if not deduped:
            return {"inserted": 0, "updated": 0}

        await self._ensure_connected()
        existing = await self._read_indexed()
        # Key value -> the existing records (a list, in case legacy data has duplicates).
        by_key: Dict[Any, List[Dict[str, Any]]] = {}
        for record in existing:
            by_key.setdefault(record.get(key), []).append(record)

        to_append: List[List[Any]] = []
        update_requests: List[Dict[str, Any]] = []
        sheet_id: Optional[int] = None
        for key_value, record in deduped.items():
            matches = by_key.get(key_value)
            if matches:
                if sheet_id is None:
                    sheet_id = await self._tab_id()
                for existing_row in matches:
                    merged = self._merge(existing_row, record)
                    update_requests.append(
                        self._update_cells_request(sheet_id, existing_row["_row_index"], merged)
                    )
            else:
                to_append.append(self._encode_row(record))

        if to_append:
            await self._append_rows(to_append)
        if update_requests:
            await execute(
                self.connection.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id, body={"requests": update_requests}
                ),
                op="upsert",
            )
        logger.info("Upserted: %d inserted, %d updated", len(to_append), len(update_requests))
        return {"inserted": len(to_append), "updated": len(update_requests)}

    async def delete(self, filters: Dict[str, Any]) -> int:
        """Delete rows matching the filters. Returns the number of rows deleted.

        Uses each record's true sheet row index (captured during ``read``), so
        duplicate rows are deleted correctly. Rows are removed bottom-up in one
        batch call so earlier indices stay valid.
        """
        self._require_sheet()
        rows = await self._read_indexed(filters)
        if not rows:
            return 0

        sheet_id = await self._tab_id()
        # Highest index first so deleting a row never shifts the ones still to delete.
        indices = sorted({record["_row_index"] for record in rows}, reverse=True)
        requests = [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": i,
                        "endIndex": i + 1,
                    }
                }
            }
            for i in indices
        ]
        await execute(
            self.connection.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id, body={"requests": requests}
            ),
            op="delete",
        )
        return len(indices)

    async def _grid_extent(self) -> tuple:
        """Return ``(sheetId, row_count)`` where row_count includes the header row."""
        sheet_id = await self._tab_id()
        result = await execute(
            self.connection.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.sheet_id, range=f"{self.schema.name}!A:A"),
            op="extent",
        )
        return sheet_id, len(result.get("values", []))

    async def chart(
        self,
        *,
        x: str,
        y: Union[str, List[str]],
        kind: str = "COLUMN",
        title: str = "",
        anchor_col: Optional[int] = None,
    ) -> int:
        """Embed a native chart in the spreadsheet (no extra dependencies).

        Plots one or more ``y`` fields against the ``x`` field using Google's own
        charting. For Python-side plots, use ``to_dataframe()`` with matplotlib or
        Plotly instead.

        Args:
            x: field name for the domain (category / x-axis).
            y: field name, or list of field names, to plot as series.
            kind: COLUMN, BAR, LINE, AREA, SCATTER, COMBO, STEPPED_AREA or PIE.
            title: chart title (defaults to the tab name).
            anchor_col: column index to drop the chart at (defaults to just right
                of the data).

        Returns:
            The new chart's id.
        """
        self._require_sheet()
        kind = kind.upper()
        if kind not in _CHART_TYPES:
            raise ValidationError(
                f"Unknown chart kind '{kind}'. Use one of: {', '.join(sorted(_CHART_TYPES))}."
            )
        y_fields = [y] if isinstance(y, str) else list(y)
        for name in [x, *y_fields]:
            if name not in self._field_map:
                raise ValidationError(
                    f"Unknown field '{name}'. Fields: {', '.join(self._field_map)}."
                )

        await self._ensure_connected()
        sheet_id, rows = await self._grid_extent()
        if rows <= 1:
            raise ValidationError("No data rows to chart — insert records first.")

        index = {field.name: i for i, field in enumerate(self.schema.fields)}

        def _source(col: int) -> Dict[str, Any]:
            return {
                "sources": [
                    {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": rows,
                        "startColumnIndex": col,
                        "endColumnIndex": col + 1,
                    }
                ]
            }

        if kind == "PIE":
            spec = {
                "title": title or self.schema.name,
                "pieChart": {
                    "legendPosition": "RIGHT_LEGEND",
                    "domain": {"sourceRange": _source(index[x])},
                    "series": {"sourceRange": _source(index[y_fields[0]])},
                },
            }
        else:
            spec = {
                "title": title or self.schema.name,
                "basicChart": {
                    "chartType": kind,
                    "legendPosition": "BOTTOM_LEGEND",
                    "headerCount": 1,
                    "domains": [{"domain": {"sourceRange": _source(index[x])}}],
                    "series": [
                        {"series": {"sourceRange": _source(index[name])}, "targetAxis": "LEFT_AXIS"}
                        for name in y_fields
                    ],
                },
            }

        anchor = anchor_col if anchor_col is not None else len(self.schema.fields) + 1
        request = {
            "addChart": {
                "chart": {
                    "spec": spec,
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId": sheet_id,
                                "rowIndex": 0,
                                "columnIndex": anchor,
                            }
                        }
                    },
                }
            }
        }
        result = await execute(
            self.connection.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id, body={"requests": [request]}
            ),
            op="chart",
        )
        chart_id = result["replies"][0]["addChart"]["chart"]["chartId"]
        logger.info("Added %s chart %s", kind, chart_id)
        return chart_id

    async def rename_sheet(self, new_title: str) -> None:
        """Rename the spreadsheet."""
        self._require_sheet()
        await self._ensure_connected()
        request = {
            "updateSpreadsheetProperties": {
                "properties": {"title": new_title},
                "fields": "title",
            }
        }
        await execute(
            self.connection.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id, body={"requests": [request]}
            ),
            op="rename",
        )
        logger.info("Renamed sheet to: %s", new_title)

    def _drive(self):
        """Build a Drive v3 client for ownership-level ops on sheets GSAB created."""
        return build("drive", "v3", credentials=self.connection.credentials)

    @property
    def csv_url(self) -> str:
        """CSV-export URL for this spreadsheet's first tab.

        Anyone can fetch it once you call ``share()`` (otherwise it needs an
        authenticated request) — handy for embedding or ``pandas.read_csv(db.csv_url)``.
        """
        self._require_sheet()
        return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/export?format=csv"

    async def share(self, *, role: str = "reader") -> str:
        """Make this spreadsheet readable by anyone with the link; return its URL.

        Adds an "anyone with the link" permission via Drive. This works on the
        default ``drive.file`` scope — GSAB owns the sheets it creates, so no broader
        or sensitive scope is needed. Idempotent; revoke with ``unshare()``.

        Args:
            role: ``"reader"`` (default, view-only) or ``"writer"`` (anyone with the
                link can edit — i.e. the public; use with care).

        Returns:
            The shareable spreadsheet URL.
        """
        if role not in ("reader", "writer"):
            raise ValidationError("share role must be 'reader' or 'writer'.")
        self._require_sheet()
        await self._ensure_connected()
        drive = self._drive()
        await execute(
            drive.permissions().create(
                fileId=self.sheet_id, body={"type": "anyone", "role": role}, fields="id"
            ),
            op="share",
        )
        meta = await execute(
            drive.files().get(fileId=self.sheet_id, fields="webViewLink"), op="share"
        )
        url = meta.get("webViewLink", f"https://docs.google.com/spreadsheets/d/{self.sheet_id}")
        logger.info("Shared spreadsheet publicly (%s): %s", role, url)
        return url

    async def unshare(self) -> None:
        """Revoke the public "anyone with the link" access added by ``share()``."""
        self._require_sheet()
        await self._ensure_connected()
        try:
            await execute(
                self._drive()
                .permissions()
                .delete(fileId=self.sheet_id, permissionId="anyoneWithLink"),
                op="unshare",
            )
            logger.info("Revoked public access: %s", self.sheet_id)
        except NotFoundError:
            pass  # already not shared — nothing to revoke

    async def delete_sheet(self) -> None:
        """Delete the entire spreadsheet via the Drive API (falls back to clearing rows)."""
        self._require_sheet()
        await self._ensure_connected()
        drive_service = self._drive()
        try:
            await execute(
                drive_service.files().delete(fileId=self.sheet_id, supportsAllDrives=True),
                op="delete_sheet",
            )
            logger.info("Deleted spreadsheet: %s", self.sheet_id)
            self.sheet_id = None
            return
        except Exception as drive_error:
            text = str(drive_error)
            if "accessNotConfigured" not in text and "has not been used" not in text:
                raise
            logger.warning("Drive API unavailable; clearing sheet contents instead.")

        # Fallback: clear all data rows when the Drive API isn't enabled.
        await execute(
            self.connection.service.spreadsheets()
            .values()
            .clear(spreadsheetId=self.sheet_id, range=f"{self.schema.name}!A2:Z"),
            op="clear",
        )
        logger.info("Cleared sheet contents: %s", self.sheet_id)
        self.sheet_id = None
