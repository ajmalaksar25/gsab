# GSAB roadmap

**Vision:** a Supabase-lite you run on your **own Google account** — a typed table store
(schemas, validation, CRUD, server-side queries, charts) on top of Google Sheets, for
small apps and prototypes that shouldn't have to pay for or operate a database. You bring
a Google account; GSAB gives it a database-like API.

This file is the source of truth for what's shipped, what's coming, and how stable each
piece is. The public summary lives at https://gsab.ajmalaksar.com/#roadmap.

## Stability levels

| Level | Meaning |
|---|---|
| **Stable** | Production-ready; documented; semver-protected. |
| **Beta** | Works and documented, API may still change before it's Stable. |
| **Experimental** | Shipped early so you can try it; rough edges; **may change or be removed**; rolled out gradually. Clearly flagged in the docs. |
| **Planned** | Decided, not built yet. |
| **Researching** | We want it; feasibility/design is open (often constrained by what Google Sheets allows). |
| **Out of scope** | Won't fit Sheets well — documented with the reason and a workaround. |

### Docs policy

- A feature is documented on the site/docs when it reaches **Stable**.
- If something **Beta/Experimental is already shipped**, it IS mentioned — clearly labeled
  (Beta/Experimental), with a note that the API may change and whether it's rolling out
  gradually. We never ship a capability silently.
- Each release keeps README ↔ site `/#roadmap` ↔ docs/`llms` in sync (see `AGENTS.md`).

## Available now — Stable

- **Auth**: friction-free `gsab auth login` (minimal `drive.file` scope, no Cloud project);
  service-account + gcloud for servers. Tokens auto-refresh; a failed/revoked refresh →
  `AuthError`.
- **Schema as an ORM-lite**: `Schema` + `Field`/`FieldType`, `create_sheet()` = define and
  create a "table". Validation on every write: `required`, types, `min/max`, `min_length/
  max_length`, **regex `pattern`**, custom `validation_rules`.
- **Async CRUD** + rich `read()` filters (`$eq $ne $gt $gte $lt $lte $in $nin $contains
  $regex`), `bulk_insert`, type-correct **server-side `query()`** (Google Visualization).
- **Enforced keys + `upsert()`**: a `primary_key`/`unique` field is checked on write — a
  duplicate `insert` raises `DuplicateKeyError`; `upsert()`/`bulk_upsert()` do idempotent
  insert-or-update keyed on the PK. It's a read-check-write (Sheets has no conditional
  write), so concurrent inserts of the same *new* key can still race — documented, not hidden.
- **Charts** (native in-sheet `chart()`), **pandas bridge** (`to_dataframe`/`from_dataframe`).
- **Public sharing**: `share()` makes a created sheet readable by anyone with the link (returns
  the URL), `unshare()` revokes, `csv_url` is the export URL. Stays on the non-sensitive
  `drive.file` scope — GSAB owns the sheets it creates. Only sheets GSAB created, not a user's
  pre-existing ones.
- **Field encryption** (Fernet).
- **LLM-friendly errors** + retry/backoff; **installable skills** (`gsab skill install`).
- **Get-productive-fast CLI**: `gsab doctor [--live]` (verify auth + a live round-trip),
  `gsab init [--fastapi]` (scaffold a runnable project / FastAPI CRUD service),
  `gsab import <csv>` (infer a schema + load a CSV), `gsab cookbook list|show` (ready recipes).
- **Multiple independent connections to the same sheet** — verified: separate
  `SheetConnection`s on one sheet read each other's writes.

### Concurrency & consistency model (Stable knowledge — verified on real sheets)

- **Parallel writes don't get lost**: N concurrent inserts from N separate connections all
  land (Google inserts appends atomically).
- **Updates are last-write-wins**: concurrent updates to the same row leave one value and an
  intact row — there are **no transactions and no locking** (Sheets has none).
- **Keys are enforced best-effort**: `primary_key`/`unique` are checked with a read before
  the write, so duplicates from a single client are rejected — but two clients inserting the
  same new key concurrently can both succeed (no conditional write). `upsert()` closes the
  single-client idempotency gap; for strict cross-client uniqueness, serialize the writes.
- **Reads are eventually consistent**; rate limits apply (≈300 reads/min, 60 writes/min per
  project by default).
- Guidance: treat GSAB as an append-friendly, last-write-wins store. For write-heavy or
  strongly-consistent needs, put a queue in front or use a real database.

## Next — Beta / Planned

- **Rate-aware batching / pooling** — saturate the ~300 req/min budget safely (shared auth +
  reusable clients + a batching layer), not persistent DB connections. *(Planned)*
- **Pipe-friendly CLI** — JSON in/out so `gsab ... | jq` and stdin import work. *(Planned)*

## Experimental (shipped early, flagged in docs)

- **Reactive / "realtime" reads** — Google Sheets has **no change-stream/push** for cell
  edits, so true realtime (Supabase/Convex style) isn't possible directly. Planned approach:
  a `watch()`/reactive layer that **polls + diffs + emits changes**, with helpers to drive a
  Python UI or an HTML/websocket auto-refresh. Will ship Experimental and labeled as polling,
  not push. *(Researching → Experimental)*
- **Form → sheet sync** — a custom app form calls `insert()` on submit (works today); Google
  Forms already write to a linked sheet which GSAB reads. A turnkey "form table stays in
  sync" helper builds on the reactive layer. *(Planned/Experimental)*

## Researching / later

- **Relations / joins** — Sheets has no foreign keys or joins; a client-side join helper
  across sheets is feasible (read + join in Python), not DB-enforced. *(Researching)*
- **Optimistic concurrency** — a `version` column + read-check-write to detect conflicts
  (still racy without conditional writes). *(Researching)*
- **Connection pooling semantics** — for Sheets this means rate-limited concurrency + shared
  auth across reusable clients, plus a batching layer; not persistent DB connections.
  *(Researching)*
- **MCP server** (drive sheets from Claude), **TUI**, **hosted easy-mode auth broker**. *(Planned)*

## Out of scope (and why)

- **ACID transactions / multi-row atomicity** — Sheets offers none; only per-`batchUpdate`
  atomicity. Use a real DB if you need this.
- **SQL joins / foreign-key constraints**, **row-level security**, **true realtime push** —
  not available from the Sheets API. We approximate where we can (joins in Python, polling)
  and say so.
- **Very large / high-QPS workloads** — Sheets caps (~10M cells/sheet) and per-minute rate
  limits make GSAB a fit for small-to-medium apps and prototypes, not high-scale OLTP.

## Coming from Supabase?

You can rebuild a meaningful slice on your own Google account, at $0: typed tables + schema
validation, CRUD, server-side queries, charts, and auth — without realtime push, SQL joins,
RLS, or transactions. Realtime is approximated by polling; relations are app-side. For a
small client who doesn't want to pay for or run a database, that trade is often worth it.
