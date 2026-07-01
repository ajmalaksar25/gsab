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

## SheetManager(connection, schema, encryption_key=None, *, policy=None)

`policy` is an `AccessPolicy` (see below) enforced on every operation — read-only, sheet allowlist, share-role cap, destructive-confirm, and an activity feed. Defaults to a permissive policy.

- `await create_sheet(title) -> str` — create the spreadsheet, return its id.
- `await insert(data: dict) -> None`
- `await bulk_insert(records: list[dict]) -> int` — many rows in one append; returns count. Rejects a duplicate `unique`/`primary_key` value with `DuplicateKeyError`.
- `await upsert(data: dict, *, key=None) -> "inserted" | "updated"` — insert, or update the row whose key matches (default key = the schema's primary key). Omitted fields keep their current value.
- `await bulk_upsert(records: list[dict], *, key=None) -> {"inserted": int, "updated": int}` — batch insert-or-update; last entry wins per key. One append + one batched update. Read-check-write (no conditional write), so concurrent inserts of the same new key can race.
- `await read(filters: dict | None = None) -> list[dict]` — dicts keyed by field name, schema-typed.
  - Filters: `{field: value}` (equality) or `{field: {op: value}}`.
  - Operators: `$eq $ne $gt $gte $lt $lte $in $nin $contains $regex`.
- `watch(*, interval=2.0, filters=None, key=None, emit_initial=True)` — **async generator (Experimental)**. Polls + diffs, yields `{"added", "updated", "removed"}` change sets (keyed on the primary key); sees writes from any connection or the Google UI. Polling (~interval s), not push. Run ONE watcher per sheet and fan out to N viewers (SSE/WebSocket) — see `gsab cookbook show realtime_api`. `async for change in db.watch(): ...`
- `await update(filters: dict, updates: dict) -> int` — rows changed.
- `await delete(filters: dict, *, confirm=False) -> int` — rows deleted (handles duplicate rows correctly). If the policy sets `confirm_destructive`, pass `confirm=True`.
- `await query(sql: str) -> list[dict]` — server-side Google Visualization query. Columns are letters; `column(name)` maps a field to its letter. Schema columns come back typed/decrypted; aggregates stay gviz-native.
- `column(field_name: str) -> str` — e.g. `"A"`.
- `await to_dataframe(filters=None)` / `await from_dataframe(df) -> int` — needs `gsab[pandas]`.
- `await chart(*, x, y, kind="COLUMN", title="", anchor_col=None) -> int` — native in-sheet chart. `kind`: COLUMN, BAR, LINE, AREA, SCATTER, COMBO, STEPPED_AREA, PIE. `y` may be a field or list of fields.
- `await rename_sheet(new_title) -> None`
- `await share(*, role=None) -> str` — make the sheet public (anyone with the link), return its URL. `role` `"reader"`/`"commenter"`/`"writer"` (the Sheets UI term `"editor"` is an alias for `"writer"`); defaults to the policy's `default_share_role` ("reader") and is capped by its `max_share_role`. Works on the `drive.file` scope (GSAB owns sheets it creates); only for GSAB-created sheets.
- `await unshare() -> None` — revoke public access. `csv_url` (property) — the CSV-export URL (public once shared).
- `await delete_sheet() -> None`

## AccessPolicy — client-side guardrails

`AccessPolicy(...)` — construct in Python and pass to `SheetManager(..., policy=...)`, or save/load as a small JSON profile to share one config across the library, the MCP server and the TUI. A guardrail layer for safety/control/visibility — **not** the security boundary (that stays the OAuth scope; a determined caller of the raw library can bypass it). Blocked actions raise `PolicyError`.

- `read_only=False` — block every mutation (create/insert/update/upsert/delete/share).
- `allowed_sheets=None` — id allowlist on top of the `drive.file` floor; `None` = any the credential can reach. A sheet GSAB *created* is always allowed. Enforced before any network call.
- `allow_share=True`, `default_share_role="reader"`, `max_share_role="writer"` — whether `share()` is allowed at all, the role used when none is passed, and the highest role it may grant (set `max_share_role="reader"` to forbid public-edit).
- `confirm_destructive=False` — require `confirm=True` on destructive ops (`delete`).
- `on_activity=None` — callback fired with one event dict per op (`{"op", "sheet_id", ...}`) — the feed a TUI / MCP-UI renders. Never allowed to break an operation.
- `policy.save(path)` / `AccessPolicy.load(path)` — JSON profile round-trip (the `on_activity` hook is not stored).

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
| `PolicyError` | An `AccessPolicy` guardrail blocked the action (read-only, sheet not allowed, share-role cap, needs `confirm=True`). |
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
gsab mcp [--read-only] [--policy PATH]   # MCP server (needs `pip install "gsab[mcp]"`)
gsab tui [--policy PATH]                  # access-control TUI (needs `pip install "gsab[tui]"`)
```

- `mcp --read-only` — expose only the read/query tools (no create/insert/update/delete/share).
- `mcp --policy PATH` — run under an `AccessPolicy` JSON profile (allowed sheets, share-role cap, etc.).
- `tui` — a terminal cockpit to edit an `AccessPolicy`, probe what it allows/blocks, and watch a live `on_activity` feed; save/loads the same JSON profile `--policy` reads.

## MCP server

`gsab mcp` runs a Model Context Protocol server (stdio) so ANY MCP client (Claude Desktop/Code, Codex, Cursor, Zed, Cline, OpenCode, …) can use a sheet as a database. Tools: `create_sheet(title, columns, primary_key?)`, `columns`, `insert`, `read`, `update`, `delete`, `upsert`, `query`, `share`. Uses your existing GSAB auth. Configure the client to run command `gsab` with args `["mcp"]`.

Access control: `gsab mcp --read-only` registers only the read/query tools; `gsab mcp --policy profile.json` binds an `AccessPolicy` (allowed sheets enforced before any network call, share-role cap, destructive-confirm). The `delete` tool is labeled destructive and returns an explicit "permanent, cannot be undone" warning. Embedding: `from gsab.mcp.server import build_server; build_server(read_only=..., policy=...)`.

Env vars: `GSAB_NO_KEYRING=1` (skip the OS keychain — fixes macOS re-prompts), `GSAB_NO_UPDATE_CHECK=1` (silence the update notice), `GSAB_SERVICE_ACCOUNT` (headless auth).
