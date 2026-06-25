# GSAB — Google Sheets as a Backend

[![PyPI](https://img.shields.io/pypi/v/gsab.svg)](https://pypi.org/project/gsab/)
[![Python](https://img.shields.io/pypi/pyversions/gsab.svg)](https://pypi.org/project/gsab/)
[![License: MIT](https://img.shields.io/badge/license-MIT-1b7a4b.svg)](LICENSE.md)
[![Tests](https://github.com/ajmalaksar25/gsab/actions/workflows/tests.yml/badge.svg)](https://github.com/ajmalaksar25/gsab/actions/workflows/tests.yml)

A database-like interface for Google Sheets — schemas, validation, field encryption, async CRUD, server-side queries, and a friction-free CLI. **Sign in once; no Google Cloud setup required.**

### 🌐 [gsab.ajmalaksar.com](https://gsab.ajmalaksar.com) &nbsp;·&nbsp; 📖 [Docs](https://gsab.ajmalaksar.com/docs) &nbsp;·&nbsp; 🗺️ [Roadmap](https://gsab.ajmalaksar.com/#roadmap)

## Install

```bash
pip install gsab          # core
pip install "gsab[pandas]"  # + DataFrame support
```

## Get started

```bash
gsab auth login           # browser sign-in (drive.file scope) — that's the whole setup
gsab init my-app          # scaffold a runnable starter (add --fastapi for a CRUD API)
gsab doctor --live        # prove it works end to end
```

Then define a schema and read/write your sheet. **Full usage, examples and the API → [the documentation](https://gsab.ajmalaksar.com/docs).** `gsab import data.csv` loads a CSV, and `gsab cookbook list` shows ready recipes.

## Features

- **Friction-free auth** — `gsab auth login` opens a browser and uses the minimal `drive.file` scope. No Cloud project, no JSON keys. DIY modes cover existing sheets, your own OAuth client, gcloud, and service accounts.
- **Schemas, keys & validation** — typed fields, validation rules, and enforced `primary_key` / `unique` columns checked on every write.
- **Field encryption** — flag a field `encrypted=True` and it's sealed before it reaches the sheet.
- **Async CRUD + upsert** — `insert / read / update / delete` plus `upsert()` for idempotent insert-or-update on a primary key, with rich filters (`$gt / $in / $contains / $regex` and more).
- **Server-side queries** — `query()` runs the Google Visualization query language (filter, sort, aggregate) on Google's side, not in Python. Values come back type-correct.
- **Reactive `watch()`** *(Experimental)* — an async generator that polls + diffs and emits `{added, updated, removed}`, seeing writes from any connection or the Google UI — drive a live, auto-updating UI. Polling (~1–2s), not push; one poller fans out to many viewers (see `examples/realtime-demo/`).
- **pandas bridge** — `to_dataframe()` / `from_dataframe()` and `bulk_insert()` for the whole analytics ecosystem.
- **Native charts** — `chart()` embeds a Google chart in the sheet; or hand `to_dataframe()` to matplotlib/Plotly.
- **One-call public sharing** — `share()` publishes a created sheet to a read-only public link (and `csv_url` for embedding); `unshare()` revokes. No extra scope — GSAB owns the sheets it makes.
- **Actionable errors** — Google API errors become clear GSAB exceptions with retry/backoff and token refresh — readable by humans and LLM agents.
- **Installable agent skills** — `gsab skill install` drops GSAB skills into `.claude/skills` (or `--portable` for any LLM) so your coding agent knows the real API.
- **Secure tokens** — stored in your OS keychain (keyring), with a 0600-file fallback.

## Roadmap

**Shipped (v0.7.0):** auth + CLI · schemas, validation & encryption · async CRUD · upsert + enforced primary keys · type-correct server-side query · **reactive `watch()` (Experimental)** · one-call public sharing · pandas bridge + bulk insert · native in-sheet charts · LLM-friendly errors + retry/backoff · installable agent skills · scaffolding & CSV import (`gsab init` / `import` / `doctor` / `cookbook`) · keychain storage.

**Coming next:** auto update-available notice · rate-aware batching · MCP server (use your sheets from Claude) · improved/pipe-friendly CLI · a JavaScript client · terminal UI · one-click hosted sign-in.

Full roadmap with per-feature stability (and what's deliberately out of scope) → [ROADMAP.md](ROADMAP.md). Live summary → [gsab.ajmalaksar.com/#roadmap](https://gsab.ajmalaksar.com/#roadmap).

## Releases

Versioned with [SemVer](https://semver.org); see [CHANGELOG.md](CHANGELOG.md). Tagged releases (`vX.Y.Z`) publish to PyPI automatically via GitHub Actions.

## License

MIT — see [LICENSE.md](LICENSE.md). GSAB is an independent project, not affiliated with Google LLC.
