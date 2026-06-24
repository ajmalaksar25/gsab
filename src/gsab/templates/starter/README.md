# My GSAB app

A starter project using [GSAB](https://gsab.ajmalaksar.com) — Google Sheets as a Backend.

## Run

```bash
pip install gsab        # add "gsab[pandas]" for DataFrames
gsab auth login         # one-time browser sign-in (no Google Cloud setup)
python app.py
```

- `schema.py` — your table (fields, types, validation).
- `app.py` — creates a sheet and does CRUD + a server-side query + a chart.

## Want your coding agent to help?

```bash
gsab skill install      # teaches Claude Code / Cursor the GSAB API
gsab skill install --portable   # or a GSAB_LLMS.md to paste into any LLM
```

Docs: https://gsab.ajmalaksar.com/docs
