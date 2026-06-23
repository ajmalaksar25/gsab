"""GSAB exception hierarchy.

Every error inherits from ``GSABError``, so callers — and LLM agents driving the
library — can catch one type and read a plain-language message that says what
went wrong and what to do about it.
"""


class GSheetsDBException(Exception):
    """Base exception for the GSAB library."""


# Friendly alias for the package base exception.
GSABError = GSheetsDBException


class AuthError(GSABError):
    """Authentication or credential resolution failed (e.g. an expired login)."""


class ConnectionError(GSABError):
    """Could not reach or build the Google Sheets API service."""


class NotFoundError(GSABError):
    """The spreadsheet, tab or row does not exist."""


class PermissionDeniedError(GSABError):
    """The authenticated account is not allowed to access this spreadsheet."""


class QuotaExceededError(GSABError):
    """Google's rate limit or quota was hit; back off and retry later."""


class ValidationError(GSABError, ValueError):
    """A record, filter or argument was rejected before reaching the API.

    Also a ``ValueError`` so existing ``except ValueError`` callers keep working.
    """


class EncryptionError(GSABError):
    """An encryption or decryption operation failed."""


class APIError(GSABError):
    """The Google Sheets API returned an unexpected error."""
