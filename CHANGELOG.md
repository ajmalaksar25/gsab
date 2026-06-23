# Changelog

All notable changes to GSAB are documented here. This project follows [Semantic Versioning](https://semver.org).
Tagged releases (`vX.Y.Z`) publish to PyPI automatically.

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
