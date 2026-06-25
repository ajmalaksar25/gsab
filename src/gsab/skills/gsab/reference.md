# GSAB API reference

Async unless noted. Import from `gsab`.

## Schema & fields

- `Schema(name: str, fields: list[Field])` — names the tab and declares its columns.
- `Field(name, field_type, required=True, unique=False, primary_key=False, default=None, min_length=None, max_length=None, pattern=None, min_value=None, max_value=None, validation_rules=None, encrypted=False)`
  - `primary_key=True` implies `required` + `unique` and is the default `upsert()` key (max one per schema). `unique=True` is enforced on insert/upsert via read-check-write (`DuplicateKeyError`).
  - All constraints are enforced on every write: `min_value`/`max_value`, `min_length`/`max_length`, `pattern`, and custom `validation_rules`. A field with a `default` is optional.
- `FieldType.{STRING, INTEGER, FLOAT, BOOLEAN, DATE, DATETIME, JSON}` — converted/validated on write, coerced back on read. `JSON` stores a `dict`/`list` and round-trips it as a structured object. (`ENCRYPTED` exists but is vestigial — use `encrypted=True` on any field instead.)
- `ValidationRule(condition: Callable[[Any], bool], error_message: str)` — custom checks.

## Connection

- `SheetConnection(credentials_path=None, *, credentials=None, service_account_file=None, scopes=None, interactive=False)`
  - `await connect()` — resolve credentials + build the client (called lazily by SheetManager).
  - `is_connected() -> bool`
  - Credential resolution order: explicit service account → cached `gsab auth login` token → gcloud ADC → (interactive browser).

## SheetManager(connection, schema, encryption_key=None)

- `await create_sheet(title) -> str` — create the spreadsheet, return its id.
- `await insert(data: dict) -> None`
- `await bulk_insert(records: list[dict]) -> int` — many rows in one append; returns count. Rejects a duplicate `unique`/`primary_key` value with `DuplicateKeyError`.
- `await upsert(data: dict, *, key=None) -> "inserted" | "updated"` — insert, or update the row whose key matches (default key = the schema's primary key). Omitted fields keep their current value.
- `await bulk_upsert(records: list[dict], *, key=None) -> {"inserted": int, "updated": int}` — batch insert-or-update; last entry wins per key. One append + one batched update. Read-check-write (no conditional write), so concurrent inserts of the same new key can race.
- `await read(filters: dict | None = None) -> list[dict]` — dicts keyed by field name, schema-typed.
  - Filters: `{field: value}` (equality) or `{field: {op: value}}`.
  - Operators: `$eq $ne $gt $gte $lt $lte $in $nin $contains $regex`.
- `await update(filters: dict, updates: dict) -> int` — rows changed.
- `await delete(filters: dict) -> int` — rows deleted (handles duplicate rows correctly).
- `await query(sql: str) -> list[dict]` — server-side Google Visualization query. Columns are letters; `column(name)` maps a field to its letter. Schema columns come back typed/decrypted; aggregates stay gviz-native.
- `column(field_name: str) -> str` — e.g. `"A"`.
- `await to_dataframe(filters=None)` / `await from_dataframe(df) -> int` — needs `gsab[pandas]`.
- `await chart(*, x, y, kind="COLUMN", title="", anchor_col=None) -> int` — native in-sheet chart. `kind`: COLUMN, BAR, LINE, AREA, SCATTER, COMBO, STEPPED_AREA, PIE. `y` may be a field or list of fields.
- `await rename_sheet(new_title) -> None`
- `await share(*, role="reader") -> str` — make the sheet public (anyone with the link), return its URL. `role` `"reader"`/`"writer"`. Works on the `drive.file` scope (GSAB owns sheets it creates); only for GSAB-created sheets.
- `await unshare() -> None` — revoke public access. `csv_url` (property) — the CSV-export URL (public once shared).
- `await delete_sheet() -> None`

## Auth helpers

- `resolve_credentials(scopes=None, *, service_account_file=None, interactive=False)`
- `login()`, `logout()`, `status()`

## Exceptions (all subclass `GSABError`)

| Exception | Meaning / fix |
|---|---|
| `AuthError` | Not signed in, or token expired/revoked → run `gsab auth login`. |
| `ConnectionError` | Could not reach Google (network drop/timeout). |
| `NotFoundError` | Spreadsheet or tab not found — check the id / tab name. |
| `PermissionDeniedError` | Account can't access the sheet, or scope not granted. |
| `QuotaExceededError` | Rate-limited; GSAB retries 429/5xx with backoff. |
| `ValidationError` | A record, filter, argument or query was rejected (also a `ValueError`). |
| `DuplicateKeyError` | A write would duplicate a `unique`/`primary_key` value — use `upsert()`. |
| `APIError` | Unexpected Google Sheets API error. |

Transient failures (429/5xx, dropped connections, timeouts) are retried automatically with exponential backoff before raising.

## CLI

```bash
gsab auth login [--full] [--client-secrets PATH] [--no-browser]
gsab auth status [--json]
gsab auth logout
gsab version
gsab help [command]
gsab skill install [--project] [--portable] [--path DIR]
```
