# GSAB API reference

Async unless noted. Import from `gsab`.

## Schema & fields

- `Schema(name: str, fields: list[Field])` — names the tab and declares its columns.
- `Field(name, field_type, required=True, unique=False, default=None, min_length=None, max_length=None, pattern=None, min_value=None, max_value=None, validation_rules=None, encrypted=False)`
- `FieldType.{STRING, INTEGER, FLOAT, BOOLEAN, DATE, DATETIME, JSON, ENCRYPTED}` — values are converted/validated on write and coerced back on read.
- `ValidationRule(condition: Callable[[Any], bool], error_message: str)` — custom checks.

## Connection

- `SheetConnection(credentials_path=None, *, credentials=None, service_account_file=None, scopes=None, interactive=False)`
  - `await connect()` — resolve credentials + build the client (called lazily by SheetManager).
  - `is_connected() -> bool`
  - Credential resolution order: explicit service account → cached `gsab auth login` token → gcloud ADC → (interactive browser).

## SheetManager(connection, schema, encryption_key=None)

- `await create_sheet(title) -> str` — create the spreadsheet, return its id.
- `await insert(data: dict) -> None`
- `await bulk_insert(records: list[dict]) -> int` — many rows in one append; returns count.
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
