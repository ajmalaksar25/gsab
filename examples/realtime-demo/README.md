# GSAB realtime demo — side-by-side, actually live

A two-pane proof that GSAB's reactive `watch()` is real:

- **Left:** the actual Google Sheet, embedded and editable.
- **Right:** your app — a table driven by `watch()` over Server-Sent Events.

Edit a cell on the left and the right pane updates within ~1s, with no refresh. One
`watch()` poller fans out to every connected browser (so N viewers cost one poll loop).

> Experimental: this is **polling (~1s), not push** — Google Sheets has no change stream.
> Perfect for dashboards, internal tools and small-team collaboration; not for
> high-frequency writes or strict transactions.

## Run it

```bash
pip install gsab fastapi uvicorn
gsab auth login          # one-time browser sign-in
python server.py         # creates + shares a demo sheet, then serves the page
# open http://127.0.0.1:8137  (the sheet's edit URL is printed in the console)
```

The server creates a fresh "GSAB realtime demo" sheet, seeds it, shares it (so the
left-pane iframe can embed it), and deletes it on shutdown. To reuse a sheet of your
own instead, set `GSAB_DEMO_SHEET_ID` to its id.

## Record the side-by-side video

1. `python server.py`, open `http://127.0.0.1:8137` (be signed in to the Google
   account that owns the sheet, so the left iframe is editable).
2. Screen-record the window. In the **left** pane, edit a cell — change a `status`
   from `todo`/`doing` to `done`, rename a task, or add a row.
3. Watch the **right** pane update (with a green flash) within ~1s. That's the shot.

## How it works

`server.py` is a ~70-line FastAPI app: a single `db.watch(interval=1.0)` loop pushes
`{added, updated, removed}` change sets to a queue per connected client; `/events`
streams them as SSE; `index.html` renders them into a live table. The same pattern
ships as a cookbook recipe: `gsab cookbook show realtime_api`.
