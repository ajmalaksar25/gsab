"""GSAB — Google Sheets as a Backend.

A database-like interface for Google Sheets: schemas, validation, field
encryption and async CRUD, with auto-detecting authentication.
"""

__version__ = "0.3.1"

from .auth import login, logout, resolve_credentials, status
from .core.connection import SheetConnection
from .core.schema import Field, FieldType, Schema, ValidationRule
from .core.sheet_manager import SheetManager
from .exceptions import (
    APIError,
    AuthError,
    ConnectionError,
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
    "APIError",
]
