---
name: gsab-fastapi
description: >
  Build a FastAPI REST backend on top of GSAB (Google Sheets as a Backend), so a Google
  Sheet is your database. Use when creating CRUD API endpoints, wiring FastAPI to GSAB,
  sharing a SheetManager across requests, or mapping GSAB errors to HTTP responses.
  Assumes the `gsab` skill for the core GSAB API.
---

# FastAPI on GSAB

A REST API whose database is a Google Sheet. GSAB's data methods are async, so they
`await` cleanly inside FastAPI route handlers. Share one `SheetManager` across requests
via the lifespan, and map `GSABError` subclasses to HTTP status codes.

## Install

```bash
pip install gsab fastapi uvicorn
gsab auth login        # or set GSAB_SERVICE_ACCOUNT for servers/CI
```

## api.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gsab import (
    SheetConnection, SheetManager, Schema, Field, FieldType,
    GSABError, NotFoundError, ValidationError, DuplicateKeyError, AuthError,
)

schema = Schema("users", [
    Field("id",   FieldType.INTEGER, primary_key=True),          # enforced unique key
    Field("name", FieldType.STRING,  required=True, max_length=80),
    Field("plan", FieldType.STRING,  default="free"),            # default => optional
])

db = SheetManager(SheetConnection(), schema)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bind a spreadsheet once at startup. Create one, or point at an existing id:
    #   db.sheet_id = "1AbC...your-id"
    await db.create_sheet("Users API DB")
    yield

app = FastAPI(title="Users API on GSAB", lifespan=lifespan)

class UserIn(BaseModel):
    id: int
    name: str
    plan: str = "free"

class UserPatch(BaseModel):
    name: str | None = None
    plan: str | None = None

@app.post("/users", status_code=201)
async def create_user(user: UserIn):
    await db.insert(user.model_dump())   # duplicate id -> DuplicateKeyError -> 409
    return user

@app.put("/users/{user_id}")
async def put_user(user_id: int, user: UserIn):
    # Idempotent create-or-replace, keyed on the primary key.
    status = await db.upsert({**user.model_dump(), "id": user_id})
    return {"result": status}

@app.get("/users")
async def list_users(plan: str | None = None):
    return await db.read({"plan": plan} if plan else None)

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    rows = await db.read({"id": user_id})
    if not rows:
        raise HTTPException(404, "user not found")
    return rows[0]

@app.patch("/users/{user_id}")
async def update_user(user_id: int, patch: UserPatch):
    changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    n = await db.update({"id": user_id}, changes)
    if not n:
        raise HTTPException(404, "user not found")
    return {"updated": n}

@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    n = await db.delete({"id": user_id})
    if not n:
        raise HTTPException(404, "user not found")
    return {"deleted": n}
```

## Map GSAB errors to HTTP

Add one exception handler so library errors become clean responses:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

STATUS = {DuplicateKeyError: 409, ValidationError: 422, NotFoundError: 404, AuthError: 401}

@app.exception_handler(GSABError)
async def gsab_error_handler(request: Request, exc: GSABError):
    code = next((s for cls, s in STATUS.items() if isinstance(exc, cls)), 502)
    return JSONResponse(status_code=code, content={"error": str(exc)})
```

## Run

```bash
uvicorn api:app --reload
# POST /users {"id":1,"name":"Ada","plan":"pro"}
# GET  /users?plan=pro
```

## Notes

- Google Sheets has no transactions and serializes writes (last-write-wins); for
  write-heavy or highly concurrent APIs treat it as eventually-consistent, or put a
  queue/cache in front. Reads are fine to fan out.
- For headless deploys use a service account (`GSAB_SERVICE_ACCOUNT`) and share the
  sheet with its email — see the `gsab` skill's recipes.
- Heavy filtering/sorting/aggregation? Push it server-side with `db.query(...)` instead
  of fetching all rows.
