"""GSAB — Google Sheets as a Backend.

A database-like interface for Google Sheets: typed schemas, validation, field
encryption, async CRUD and server-side queries, with friction-free auth.

Quickstart::

    import asyncio
    from gsab import SheetConnection, SheetManager, Schema, Field, FieldType

    schema = Schema("users", [
        Field("id",   FieldType.INTEGER, primary_key=True),
        Field("name", FieldType.STRING),
        Field("plan", FieldType.STRING, default="free"),
    ])

    async def main():
        db = SheetManager(SheetConnection(), schema)
        await db.create_sheet("My App DB")           # creates the spreadsheet
        await db.insert({"id": 1, "name": "Ada", "plan": "pro"})
        await db.upsert({"id": 1, "plan": "free"})    # idempotent — updates id=1
        rows = await db.read({"plan": "free"})        # filter
        hits = await db.query("SELECT A, B WHERE C = 'free'")  # server-side (C = plan)

    asyncio.run(main())

Authenticate once from the CLI — ``gsab auth login`` — then no Google Cloud
setup is needed.

Key types:
    SheetConnection            resolve credentials and build the API client.
    Schema / Field / FieldType define a tab's columns, types and validation.
    SheetManager               async create / insert / read / update / delete /
                               ``upsert()``, server-side ``query()``, native ``chart()``,
                               reactive ``watch()`` (Experimental) and public ``share()``.

Errors: every exception subclasses ``GSABError`` — ``AuthError``,
``ConnectionError``, ``NotFoundError``, ``PermissionDeniedError``,
``QuotaExceededError``, ``ValidationError``, ``DuplicateKeyError``,
``APIError`` — with messages written to be actionable for people and LLM
agents alike.

Full documentation: https://gsab.ajmalaksar.com/docs
"""

__version__ = "0.7.1"

from .auth import login, logout, resolve_credentials, status
from .core.connection import SheetConnection
from .core.schema import Field, FieldType, Schema, ValidationRule
from .core.sheet_manager import SheetManager
from .exceptions import (
    APIError,
    AuthError,
    ConnectionError,
    DuplicateKeyError,
    GSABError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    ValidationError,
)

__all__ = [
    "SheetConnection",
    "Schema",
    "Field",
    "FieldType",
    "ValidationRule",
    "SheetManager",
    "resolve_credentials",
    "login",
    "logout",
    "status",
    "GSABError",
    "AuthError",
    "ConnectionError",
    "NotFoundError",
    "PermissionDeniedError",
    "QuotaExceededError",
    "ValidationError",
    "DuplicateKeyError",
    "APIError",
]
