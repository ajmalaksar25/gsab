"""Recipe: a real-time table over a sheet — ONE watch() poller fans out to N browsers via SSE.

The key pattern for realtime on Sheets: don't make each browser poll Google (N x the
rate cost). Run a single `watch()` loop on the server and broadcast its change events to
every connected client over Server-Sent Events. 5 viewers = 1 poll loop.

    pip install gsab fastapi uvicorn
    export GSAB_SHEET_ID=<a sheet you created with GSAB>
    uvicorn realtime_api:app
    # browser: new EventSource("/events").onmessage = e => render(JSON.parse(e.data))

Experimental: polling (~2s), not push — Google Sheets has no change stream. Great for
dashboards / internal tools / small-team collab; not for high-frequency writes.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from gsab import Field, FieldType, Schema, SheetConnection, SheetManager

schema = Schema(
    "rows",
    [
        Field("id", FieldType.INTEGER, primary_key=True),
        Field("name", FieldType.STRING),
        Field("value", FieldType.FLOAT, default=0.0),
    ],
)

db = SheetManager(SheetConnection(), schema)
subscribers: set[asyncio.Queue] = set()


async def _poller():
    # One watcher for the whole server; push each change set to every subscriber.
    async for change in db.watch(interval=2.0):
        for q in list(subscribers):
            q.put_nowait(change)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.sheet_id = os.environ["GSAB_SHEET_ID"]  # an existing sheet you created
    task = asyncio.create_task(_poller())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/events")
async def events():
    """SSE stream of {added, updated, removed} change sets for all viewers."""
    q: asyncio.Queue = asyncio.Queue()
    subscribers.add(q)

    async def gen():
        # Send current rows first so a freshly-connected browser renders immediately.
        rows = await db.read()
        yield f"data: {json.dumps({'added': rows, 'updated': [], 'removed': []}, default=str)}\n\n"
        try:
            while True:
                change = await q.get()
                yield f"data: {json.dumps(change, default=str)}\n\n"
        finally:
            subscribers.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
