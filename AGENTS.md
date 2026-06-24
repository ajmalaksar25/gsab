# GSAB — agent & contributor guide

GSAB ("Google Sheets as a Backend") is a Python library + CLI that treats a Google
Spreadsheet like a database. Source lives in `src/gsab/`; it ships to PyPI as `gsab`.
The marketing site + docs live in the separate **gsab-frontend** repo (deploys to
gsab.ajmalaksar.com).

This file is the **canonical, tool-agnostic** instruction set. Keep all shared
conventions here — `CLAUDE.md` just imports it, and other agent tools read `AGENTS.md`
directly. Add new shared rules here, not in tool-specific files. Personal / machine-local
notes go in `CLAUDE.LOCAL.md` (untracked; see `.git/info/exclude`).

## Engineering guidelines
- Terse, simple, plug-and-play code. No redundant abstraction, no re-wrapping a function
  for no benefit. Match the surrounding style and comment density.
- Readable by humans **and** by LLM/agents.
- The public API carries real docstrings (Args / Returns / Raises) so `help()` reads like
  the standard library. Plain text — no Sphinx `:role:` markup that leaks into `help()`.

## Errors are first-class
- Every exception subclasses `GSABError` (`src/gsab/exceptions/`). Messages must be
  actionable for end-users **and** LLM agents (GSAB is driven via Claude / MCP).
- Map Google `HttpError` → friendly GSAB types in `src/gsab/utils/errors.py`; always chain
  with `raise ... from e`.
- Transient failures (429/5xx, dropped connections, timeouts) auto-retry with backoff; a
  failed/expired token refresh maps to `AuthError` ("run `gsab auth login`").

## How changes are added & verified
- Lint/format: `ruff check` + `ruff format` (line-length 100). Tests: `pytest`
  (`asyncio_mode=auto`), offline-first (mock the Google client).
- **Verify beyond the happy path**: exercise error paths, network failure, and token
  renewal — not only the success case.
- **Verify on a clean external install**, not just the dev `.venv`: `pip install` the
  built/published package into a fresh environment and run the real flow (e.g.
  `gsab auth login`). Three onboarding bugs in a row (default scope → missing bundled
  client → UTF-8 BOM) each surfaced ONLY this way. Confirm the bundled client actually
  *parses* through the login path, not just that the file exists.
- Prove library correctness against independently-computed expectations — never bend a
  test to whatever the code happens to return.

## Release flow (SemVer · trusted publishing)
1. Bump `__version__` in `src/gsab/__init__.py`.
2. Add a `CHANGELOG.md` entry.
3. Keep these in sync: the README roadmap, the site `/#roadmap`, and the docs/`llms` files
   (in gsab-frontend — run `npm run docs` there after editing `content/docs/*.md`).
4. `git tag vX.Y.Z && git push origin vX.Y.Z` → `.github/workflows/publish.yml` injects the
   bundled OAuth client (BOM-stripped), builds sdist + wheel, and publishes to PyPI via
   trusted publishing. No token, no manual upload.
- The bundled client must land in **both** sdist and wheel (`[tool.hatch.build].artifacts`),
  because `build` produces the wheel *from* the sdist.

## Roadmap & docs stability

- `ROADMAP.md` is the source of truth for direction and per-feature stability
  (Stable / Beta / Experimental / Planned / Researching / Out of scope). The site
  `/#roadmap` is the public summary.
- **Docs policy:** document a feature on the site/docs when it's **Stable**. If something
  Beta/Experimental is already shipped, still mention it — clearly labeled, noting the API
  may change and whether it's rolling out gradually. Never ship a capability silently.
- Be honest about Google Sheets' limits (no transactions, no SQL joins/FK, no realtime push,
  rate limits) — document the constraint and the workaround rather than implying parity with
  Postgres/Supabase.

## Secrets & ignores
- Never commit secrets: `client_secret*.json`, `*service-account*.json`, tokens
  (gitignored; GitHub push protection enforces). The public client is non-confidential and
  injected only at publish time from the `GSAB_OAUTH_CLIENT` GitHub secret.
- lean-ctx artifacts (`.lean-ctx/`, `.ctx/`, `*.ctx`) are gitignored.

## Layout
- `src/gsab/auth/` — credential resolution + login (`resolver.py`), bundled client.
- `src/gsab/core/` — `sheet_manager.py` (CRUD / query / chart), `query.py` (gviz),
  `schema.py`, `connection.py`.
- `src/gsab/utils/errors.py` — error mapping + retry/backoff.
- `src/gsab/cli/` — Typer CLI. `tests/` — offline unit tests.
