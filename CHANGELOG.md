# Changelog

All notable changes to GSAB are documented here. This project follows [Semantic Versioning](https://semver.org).
Tagged releases (`vX.Y.Z`) publish to PyPI automatically.

## [0.10.0] — 2026-07-02

Access control gets a face — a terminal UI over `AccessPolicy`.

### Added
- **Access-control TUI** *(Experimental)* — `gsab tui` (install with `pip install "gsab[tui]"`)
  opens a terminal cockpit over `AccessPolicy`: toggle `read_only` / `allow_share` /
  `confirm_destructive`, pick the default + max share role, manage the allowed-sheets
  allowlist, and **save/load the same JSON profile `gsab mcp --policy` reads**. A **probe**
  panel shows whether any op (read / query / insert / upsert / update / delete / share /
  create_sheet) would be allowed or blocked — running the exact guardrail checks the library
  and MCP server apply — and a **live activity feed** streams the `on_activity` events an op
  emits. The policy on screen is a real `AccessPolicy`, so a `SheetManager(..., policy=...)`
  sharing it streams into the feed too.

### Fixed
- **`AccessPolicy.save()` no longer deep-copies the `on_activity` hook.** It built the profile
  dict via `dataclasses.asdict()`, which deep-copies every field *before* dropping the hook — so
  a bound-method hook (like the TUI's feed) could blow up on save. It now serializes the
  JSON-native fields directly.
- **`AccessPolicy` now canonicalizes share-role aliases at construction** (`editor` → `writer`,
  `viewer` → `reader`, …) instead of storing them verbatim. A saved profile and every consumer
  (the MCP server, the TUI's role selectors) now only ever see `reader`/`commenter`/`writer`.

## [0.9.0] — 2026-06-28

Access control + a security pass — decide exactly what the library (and an AI agent) may do.

### Added
- **`AccessPolicy`** — client-side guardrails you construct in Python and pass to `SheetManager(..., policy=...)`, or save/load as a small JSON profile (`AccessPolicy.save` / `.load`) to share the same config across the library, the MCP server and (soon) the TUI. Controls: `read_only` (block every mutation), `allowed_sheets` (an optional id allowlist on top of the `drive.file` scope floor — a sheet GSAB *created* is always allowed), `allow_share` / `default_share_role` / `max_share_role` (cap how public a `share()` may go), `confirm_destructive` (require `confirm=True` on `delete`), and an `on_activity` hook (one event per op — the feed a UI renders). A guardrail layer for safety, control and visibility — **not** the security boundary (that stays the OAuth scope). New `PolicyError` (exported from `gsab`) is raised when a guardrail blocks an action.
- **MCP access controls** — `gsab mcp --read-only` exposes only the read/query tools; `gsab mcp --policy profile.json` runs the server under an `AccessPolicy` (allowed sheets enforced before any network call, share-role cap, etc.). The `delete` tool is labeled destructive and returns an explicit "permanent, cannot be undone" warning.
- **Security CI** — a `bandit` (SAST) + `pip-audit` (dependency CVEs) GitHub Actions workflow runs on every push / PR.

### Changed
- **`share(role=...)` now accepts `reader` / `commenter` / `writer`** (the Sheets UI term "editor" is an alias for "writer"); the role defaults to the policy's `default_share_role` and is capped by `max_share_role`. (Previously only `reader` / `writer`.)

### Security
- Ran a multi-agent security review of the package (input validation, auth, crypto, deserialization, data exposure) — **no vulnerabilities found**. The one `bandit` flag — the update-check `urlopen` on a fixed HTTPS URL — is a reviewed false positive, annotated `# nosec`.

## [0.8.0] — 2026-06-26

Use your Google Sheet as a database — from Claude.

### Added
- **MCP server** — `gsab mcp` runs a Model Context Protocol server (stdio) so an MCP host (Claude Desktop / Claude Code, or any MCP client) can drive your sheets directly. Tools: `create_sheet`, `columns`, `insert`, `read`, `update`, `delete`, `upsert`, `query`, `share`. Columns are treated as text; a created sheet can declare a `primary_key` to unlock enforced uniqueness + `upsert`. Auth uses your existing GSAB credentials (`gsab auth login` or a service account). Install with `pip install "gsab[mcp]"`; configure your host to run `gsab mcp`.

## [0.7.2] — 2026-06-26

### Fixed
- **0.7.1's CLI crashed on Python 3.9.** The new update-check module used a PEP 604 `str | None` annotation, which 3.9 evaluates at definition time (`TypeError: unsupported operand type(s) for |`). Added `from __future__ import annotations`. (The library API was unaffected; 0.7.1 works on 3.10+. Upgrade if you're on 3.9.)

### Changed
- The publish workflow now **gates on lint + the offline test suite (Python 3.9 and 3.12)** before publishing to PyPI — a build that fails CI can no longer be released.

## [0.7.1] — 2026-06-26

### Added
- **Update notice** — the CLI now tells you when you're behind. It checks PyPI at most once a day (cached in the config dir, non-blocking with a short timeout, and it never breaks a command), then prints a one-line *"a new gsab is available — pip install -U gsab"* to stderr. Opt out with `GSAB_NO_UPDATE_CHECK=1`.
- **`GSAB_NO_KEYRING=1`** — skip the OS keychain and store the token in the 0600 file instead. This fixes **macOS Keychain re-prompting for your password on every command** (the prompt fires when the invoking binary isn't in the keychain item's ACL — common for a CLI). A smoother default for Mac users who hit the prompt loop.

## [0.7.0] — 2026-06-25

Reactive reads — your sheet, live. *(Experimental)*

### Added
- **`SheetManager.watch(*, interval=2.0, filters=None, key=None, emit_initial=True)`** — an async generator that polls the tab, diffs against the last snapshot, and yields `{"added", "updated", "removed"}` change sets (keyed on the primary key). It sees writes from **anyone** — this library, another connection, or a person editing in the Google Sheets UI — so you can drive a live, auto-updating UI. `async for change in db.watch(): ...`
- **Realtime recipe** — `gsab cookbook show realtime_api`: the scaling pattern for many viewers — **one server-side `watch()` poller fans out to N browsers over Server-Sent Events** (don't poll once per viewer), which keeps a sheet well under the rate limit.
- **Side-by-side demo** — `examples/realtime-demo/` (`python server.py`): the real Google Sheet on the left, your `watch()`-driven app on the right, updating live as you edit.

### Notes
- **Experimental — this is polling (~1–2s), not push.** Google Sheets has no change-stream/push (verified: Sheets API has none; Drive `changes.watch` is file-level and batched ~every 3 min), so polling + diff is the portable path. Great for live dashboards, internal tools, small-team collaboration, forms/feeds, config a non-dev edits, and prototypes — **not** for high-frequency writes, strict transactions, sub-second SLAs, huge/hot tables, or many writers to the same rows. A Convex-*feel* for that envelope, not a database replacement.

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
