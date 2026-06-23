# Changelog

All notable changes to GSAB are documented here. This project follows [Semantic Versioning](https://semver.org).
Tagged releases (`vX.Y.Z`) publish to PyPI automatically.

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
