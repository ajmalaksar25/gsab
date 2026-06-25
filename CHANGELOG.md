# Changelog

All notable changes to GSAB are documented here. This project follows [Semantic Versioning](https://semver.org).
Tagged releases (`vX.Y.Z`) publish to PyPI automatically.

## [0.6.0] — 2026-06-24

Primary keys and idempotent writes — make a sheet behave like a keyed table.

### Added
- **One-call public sharing**: `await db.share()` makes the spreadsheet readable by anyone with the link and returns its URL; `await db.unshare()` revokes it; `db.csv_url` is the CSV-export URL (publicly fetchable once shared — e.g. `pandas.read_csv(db.csv_url)`). Works on the default non-sensitive `drive.file` scope, because GSAB owns the sheets it creates. (Revocation is immediate at the permission level; Google's public export cache can lag briefly.)
- **`Field(..., primary_key=True)`** — declares a table's key (implies `required` + `unique`; at most one per schema). It's the default key `upsert()` matches on.
- **`upsert(data, *, key=None)`** — insert, or update the row whose key matches; returns `"inserted"` or `"updated"`. Omitted fields keep their current value. Defaults to the schema's primary key; pass `key="field"` to match another column.
- **`bulk_upsert(records, *, key=None)`** — batch insert-or-update in one append + one batched update; last entry wins per key. Returns `{"inserted": n, "updated": m}`.
- **`DuplicateKeyError`** — raised when an `insert`/`bulk_insert` would create a duplicate `unique`/`primary_key` value (existing rows or within the same batch). Exported from `gsab`.
- `gsab cookbook show upsert` recipe; the FastAPI skill gains an idempotent `PUT` and maps `DuplicateKeyError` → HTTP 409.

### Changed
- **`unique=True` is now enforced, not advisory.** Inserting a duplicate value into a `unique`/`primary_key` field raises `DuplicateKeyError` instead of silently creating a second row. The check is a read-check-write (Google Sheets has no conditional write), so two clients inserting the *same new key* concurrently can still both land — `upsert()` closes the single-client idempotency gap; the race window is documented. Schemas with **no** unique field keep the old read-free fast append.

### Fixed
- **Field constraints are now actually enforced on writes.** `min_value` / `max_value`, `min_length` / `max_length` and custom `validation_rules` were silently ignored — `validate()` only checked the field type (plus a stray hardcoded `name == "age"` rule). They are now all enforced on every `insert` / `upsert`, as the docs always claimed, and the `age` special-case is gone (use `min_value=0`).
- **A field with a `default` is now optional.** Previously a `Field` with a `default` but `required=True` (the implicit default) was still rejected when omitted, so the `default` never applied on insert — and the 0.5.0 starter template crashed on its second insert because of it. `validate()` now treats a non-None `default` as satisfying the required check, library-wide. The starter template also demonstrates `upsert()`.
- **`FieldType.JSON` fields now round-trip as objects.** A JSON field is serialized to a JSON string on write and parsed back to the original `dict`/`list` on read; previously it fell through to `str()` and came back as an un-parseable Python-repr string.
- **The legacy `AuthenticationError` now subclasses `AuthError`** (and thus `GSABError`), so `except AuthError` / `except GSABError` catch it like every other GSAB error — it was the one exception escaping the hierarchy.

### Removed
- **The unfinished `gsab.web` FastAPI dashboard** and its `server` extra. It was shipped but undocumented, half-wired, and used the obsolete service-account-path auth model; the maintained way to build a web API on GSAB is the `gsab-fastapi` skill (`gsab skill install`). Also dropped the empty `tui` and `mcp` extras — they pulled dependencies but shipped no implementation; they'll return when those features land.

## [0.5.0] — 2026-06-24

Get productive in a minute, not an afternoon.

### Added
- `gsab doctor [--live]` — check your setup (auth, OAuth client, pandas); with `--live`, a real create → write → read → query → delete round-trip that cleans up after itself.
- `gsab init [PATH] [--fastapi]` — scaffold a runnable starter (`schema.py`, `app.py`, `README.md`); `--fastapi` adds a FastAPI CRUD service (`api.py`). Won't clobber existing files.
- `gsab import <CSV> [--title]` — infer a schema from a CSV and load it into a new sheet (needs the `pandas` extra).
- `gsab cookbook list | show <name> [--out]` — ready-to-run recipes (CSV import, server-side query, charts, encryption).

## [0.4.1] — 2026-06-24

### Fixed
- Attaching to an existing spreadsheet (`db.sheet_id = ...` without `create_sheet`) — and using **multiple independent connections to the same sheet** — now works: `read`, `insert`/`bulk_insert`, `update`, `delete`, `rename_sheet` and `delete_sheet` connect lazily on first use instead of raising `AttributeError: 'NoneType' object has no attribute 'spreadsheets'`.

### Added
- `ROADMAP.md` — direction + per-feature stability (Stable / Beta / Experimental / Planned / Researching), the docs-stability policy, and a verified concurrency/consistency model (parallel writes don't get lost; updates are last-write-wins; no transactions).

## [0.4.0] — 2026-06-24

Get productive faster, and let coding agents use GSAB.

### Added
- **Installable skills**: `gsab skill install` drops GSAB skills into `~/.claude/skills` (or `.claude/skills` with `--project`) so Claude Code and other coding agents know the real GSAB API. `--portable` writes a single `GSAB_LLMS.md` to paste into ChatGPT / Codex / Cursor / any LLM. `gsab skill list` shows what's available. Ships two skills — `gsab` (core usage + API reference + recipes) and `gsab-fastapi` (a working FastAPI-on-GSAB CRUD pattern) — bundled in the wheel.
- `gsab help [command]` — works like `--help` (people expect `gsab help`).

## [0.3.2] — 2026-06-23

### Fixed
- `gsab auth login` crashed on a fresh install with `JSONDecodeError: Unexpected UTF-8 BOM` when the bundled OAuth client carried a byte-order mark. Client secrets are now read as `utf-8-sig` (BOM-tolerant), and an unreadable/invalid client file raises a friendly `AuthError` instead of a traceback. The publish step strips a BOM and the bundled client ships clean.

### Changed
- Richer docstrings across the public API so `help(gsab)`, `help(SheetManager)`, `help(Field)` etc. read like standard-library docs — quickstart, Args / Returns / Raises, and the `GSABError` hierarchy.

## [0.3.1] — 2026-06-23

### Fixed
- Bundled OAuth client was missing from the published wheel, so a fresh `pip install gsab` could not `gsab auth login` without manual Google Cloud setup. Root cause: `build` makes the wheel from the sdist, but the client artifact was declared only for the wheel target, so it was excluded from the sdist and never reached the wheel. It's now shipped in both the sdist and the wheel. (Affected 0.2.0–0.3.0.)

## [0.3.0] — 2026-06-23

Type-correct storage (so server-side queries actually work), an LLM-friendly error layer, and native charts — validated live end-to-end and from a clean external install.

### Added
- LLM-friendly error layer: Google API errors map to clear GSAB exceptions — `NotFoundError`, `PermissionDeniedError`, `ValidationError`, `APIError` (plus existing `AuthError`, `QuotaExceededError`, `ConnectionError`) — with actionable messages for humans and LLM agents. Automatic retry/backoff on `429`/`5xx` and transient network drops/timeouts.
- Native in-sheet charts: `chart()` embeds a Google chart (COLUMN/BAR/LINE/AREA/SCATTER/COMBO/STEPPED_AREA/PIE); Python-side plots via `to_dataframe()`.

### Fixed
- **Server-side `query()` returned nothing for numeric/date filters**: cells were written as strings, so Google saw text. Values are now stored in their native type — numbers as numbers — so gviz `WHERE`/`ORDER BY` work.
- `delete()` now targets each row by its true sheet index, so duplicate rows are deleted correctly (was a fragile value-equality lookup).
- `read()` / `to_dataframe()` no longer leak the internal `_row_index` field.
- A failed/revoked token refresh now raises a friendly `AuthError` ("run `gsab auth login`") instead of a raw `RefreshError`.

### Changed
- `query()` returns columns that map to a schema field in that field's Python type (and decrypted), matching `read()`; aggregates stay gviz-native.
- Strings are stored as inert text under `RAW` input (a leading `=` is never an executable formula).

## [0.2.0] — 2026-06-23

Full rebuild from the 0.1.0 prototype into an installable library + CLI.

### Added
- Friction-free auth: `gsab auth login` (browser, minimal `drive.file` scope); DIY modes (`--full`, `--client-secrets`), gcloud ADC and service-account auto-detection.
- Typer CLI: `gsab auth login/status/logout`, `gsab version`.
- Server-side `query()` via the Google Visualization API; richer `read()` filter operators (`$eq/$ne/$gt/$gte/$lt/$lte/$in/$nin/$contains/$regex`).
- pandas bridge: `to_dataframe()` / `from_dataframe()`; `bulk_insert()` (single append for many rows).
- OS-keychain token storage (keyring), with a 0600-file fallback.

### Changed
- `src/` package layout; single-source `pyproject.toml` (hatchling) with extras `[pandas]`, `[server]`, `[tui]`, `[mcp]`, `[dev]`.
- Connection decoupled from service-account-only credentials.
- Ruff lint + format; exceptions now chain (`raise … from e`).

### Fixed
- Double-encryption of `encrypted=True` fields on insert.

### Removed
- `setup.py`, `pytest.ini`, `requirements.txt` (consolidated into `pyproject.toml`).

## [0.1.0] — 2024-12-06

Initial prototype: OAuth2 auth, schema validation, field-level encryption, async CRUD.
