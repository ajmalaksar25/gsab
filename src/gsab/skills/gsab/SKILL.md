---
name: gsab
description: >
  Use GSAB (Google Sheets as a Backend) — a Python library + CLI that treats a Google
  Spreadsheet like a database: typed schemas, validation, field encryption, async CRUD,
  server-side queries and native charts. Use when building on GSAB, signing in to Google
  Sheets, defining a schema, reading/writing/querying/charting sheet data, or debugging
  a gsab error. Real API is async: SheetConnection, SheetManager, Schema/Field/FieldType.
---

# GSAB — Google Sheets as a Backend

GSAB treats a Google Spreadsheet like a database: one tab = one table, a `Schema` gives
it typed columns + validation, and an async `SheetManager` gives you CRUD plus server-side
`query()` and native charts. Python 3.9+.

## Setup

```bash
pip install gsab              # core
pip install "gsab[pandas]"    # + DataFrame support
gsab auth login               # one browser sign-in (drive.file scope) — no Cloud project
```

## Core usage (this is the real API — it is async)

```python
import asyncio
from gsab import SheetConnection, SheetManager, Schema, Field, FieldType

schema = Schema("users", [
    Field("id",    FieldType.INTEGER, required=True, unique=True),
    Field("name",  FieldType.STRING,  required=True, max_length=80),
    Field("plan",  FieldType.STRING,  default="free"),
    Field("price", FieldType.FLOAT),
])

async def main():
    db = SheetManager(SheetConnection(), schema)   # connects lazily
    await db.create_sheet("My App DB")             # creates the spreadsheet, returns its id

    await db.insert({"id": 1, "name": "Ada", "plan": "pro", "price": 9.5})
    await db.bulk_insert([{ "id": 2, "name": "Linus", "plan": "free" }])

    rows = await db.read({"plan": "pro"})              # Python-side filter
    rows = await db.read({"price": {"$gte": 5}})       # operators: $eq $ne $gt $gte $lt $lte $in $nin $contains $regex

    hits = await db.query("SELECT A, D WHERE D = 'pro' ORDER BY A DESC")  # server-side (gviz); columns by letter
    await db.update({"id": 1}, {"plan": "team"})       # returns rows changed
    await db.delete({"plan": "free"})                  # returns rows deleted

    await db.chart(x="name", y="price", kind="COLUMN", title="Price by user")  # native in-sheet chart

asyncio.run(main())
```

## Rules of thumb

- Every data method is `async` — `await` it (run inside `asyncio.run(...)`).
- One `SheetManager` binds one `SheetConnection` + one `Schema` (one tab). `create_sheet(title)` makes a new spreadsheet; set `db.sheet_id` to use an existing one.
- Numbers/bools are stored in their real type, so server-side `query()` numeric filters work; strings stay inert text.
- Field types: `STRING, INTEGER, FLOAT, BOOLEAN, DATE, DATETIME, JSON, ENCRYPTED`. Mark a field `encrypted=True` and pass `encryption_key=` to seal it.
- Errors all subclass `GSABError` with actionable messages (e.g. `AuthError` → "run `gsab auth login`").

## Going further

- Full API surface + the error/exception hierarchy: see [reference.md](reference.md).
- Cookbook (import a CSV, server-side queries, encryption, pandas analytics): see [recipes.md](recipes.md).
- Build a REST API on GSAB: use the `gsab-fastapi` skill.
- Canonical docs: https://gsab.ajmalaksar.com/docs (and /llms-full.txt to paste into any LLM).
