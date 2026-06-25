"""GSAB realtime demo — a side-by-side proof that it actually works.

Left pane: the real Google Sheet (editable embed). Right pane: a GSAB-powered table
that updates live via `watch()` over Server-Sent Events. Edit a cell on the left and
the right pane reflects it within ~1s — genuinely, no mockups.

    pip install gsab fastapi uvicorn
    gsab auth login          # one-time
    python server.py         # opens http://127.0.0.1:8137

One `watch()` poller fans out to every connected browser, so N viewers cost one poll
loop. Experimental: polling (~1s), not push — Google Sheets has no change stream.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

from gsab import Field, FieldType, Schema, SheetConnection, SheetManager

schema = Schema(
    "tasks",
    [
        Field("id", FieldType.INTEGER, primary_key=True),
        Field("task", FieldType.STRING),
        Field("owner", FieldType.STRING, default=""),
        Field("status", FieldType.STRING, default="todo"),
    ],
)

db = SheetManager(SheetConnection(), schema)
subscribers: set[asyncio.Queue] = set()
state = {"edit_url": ""}

SEED = [
    {"id": 1, "task": "Design the schema", "owner": "Ada", "status": "done"},
    {"id": 2, "task": "Ship upsert()", "owner": "Lin", "status": "done"},
    {"id": 3, "task": "Build watch()", "owner": "Eve", "status": "doing"},
    {"id": 4, "task": "Record the demo", "owner": "You", "status": "todo"},
]


async def _poller():
    async for change in db.watch(interval=1.0):
        for q in list(subscribers):
            q.put_nowait(change)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sid = os.getenv("GSAB_DEMO_SHEET_ID")
    if sid:
        db.sheet_id = sid
    else:
        await db.create_sheet("GSAB realtime demo")
        await db.bulk_insert(SEED)
    await db.share()  # so the left-pane iframe can embed it
    state["edit_url"] = f"https://docs.google.com/spreadsheets/d/{db.sheet_id}/edit"
    print(f"\n  Demo sheet: {state['edit_url']}\n  Open:       http://127.0.0.1:8137\n")
    task = asyncio.create_task(_poller())
    yield
    task.cancel()
    if not sid:
        await db.delete_sheet()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/config")
async def config():
    return {"edit_url": state["edit_url"], "sheet_id": db.sheet_id}


@app.get("/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()
    subscribers.add(q)

    async def gen():
        rows = await db.read()  # current state on connect
        yield f"data: {json.dumps({'added': rows, 'updated': [], 'removed': []}, default=str)}\n\n"
        try:
            while True:
                change = await q.get()
                yield f"data: {json.dumps(change, default=str)}\n\n"
        finally:
            subscribers.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8137, log_level="warning")
