"""FastAPI CRUD service backed by GSAB (a Google Sheet is your database).

    pip install gsab fastapi uvicorn
    gsab auth login
    uvicorn api:app --reload
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gsab import (
    AuthError,
    GSABError,
    NotFoundError,
    SheetConnection,
    SheetManager,
    ValidationError,
)
from schema import users

db = SheetManager(SheetConnection(), users)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create a fresh sheet, or point at an existing one: db.sheet_id = "1AbC...".
    await db.create_sheet("Users API DB")
    yield


app = FastAPI(title="GSAB Users API", lifespan=lifespan)


class UserIn(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    plan: str = "free"


class UserPatch(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None


@app.post("/users", status_code=201)
async def create_user(user: UserIn):
    await db.insert(user.model_dump())
    return user


@app.get("/users")
async def list_users(plan: Optional[str] = None):
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


@app.exception_handler(GSABError)
async def gsab_error_handler(request: Request, exc: GSABError):
    status = {ValidationError: 422, NotFoundError: 404, AuthError: 401}
    code = next((s for cls, s in status.items() if isinstance(exc, cls)), 502)
    return JSONResponse(status_code=code, content={"error": str(exc)})
