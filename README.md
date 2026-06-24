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
```

Then define a schema and read/write your sheet. **Full usage, examples and the API → [the documentation](https://gsab.ajmalaksar.com/docs).**

## Features

- **Friction-free auth** — `gsab auth login` opens a browser and uses the minimal `drive.file` scope. No Cloud project, no JSON keys. DIY modes cover existing sheets, your own OAuth client, gcloud, and service accounts.
- **Schemas & validation** — typed fields, rules and uniqueness, enforced on every write.
- **Field encryption** — flag a field `encrypted=True` and it's sealed before it reaches the sheet.
- **Async CRUD + rich filters** — `insert / read / update / delete` with `$gt / $in / $contains / $regex` and more.
- **Server-side queries** — `query()` runs the Google Visualization query language (filter, sort, aggregate) on Google's side, not in Python. Values come back type-correct.
- **pandas bridge** — `to_dataframe()` / `from_dataframe()` and `bulk_insert()` for the whole analytics ecosystem.
- **Native charts** — `chart()` embeds a Google chart in the sheet; or hand `to_dataframe()` to matplotlib/Plotly.
- **Actionable errors** — Google API errors become clear GSAB exceptions with retry/backoff and token refresh — readable by humans and LLM agents.
- **Installable agent skills** — `gsab skill install` drops GSAB skills into `.claude/skills` (or `--portable` for any LLM) so your coding agent knows the real API.
- **Secure tokens** — stored in your OS keychain (keyring), with a 0600-file fallback.

## Roadmap

**Shipped (v0.4.0):** auth + CLI · schemas, validation & encryption · async CRUD · type-correct server-side query · pandas bridge + bulk insert · native in-sheet charts · LLM-friendly errors + retry/backoff · installable agent skills · keychain storage.

**Coming next:** MCP server (use your sheets from Claude) · terminal UI · real-time / reactive mode · server-side date filters · one-click hosted sign-in.

Full roadmap with per-feature stability (and what's deliberately out of scope) → [ROADMAP.md](ROADMAP.md). Live summary → [gsab.ajmalaksar.com/#roadmap](https://gsab.ajmalaksar.com/#roadmap).

## Releases

Versioned with [SemVer](https://semver.org); see [CHANGELOG.md](CHANGELOG.md). Tagged releases (`vX.Y.Z`) publish to PyPI automatically via GitHub Actions.

## License

MIT — see [LICENSE.md](LICENSE.md). GSAB is an independent project, not affiliated with Google LLC.
