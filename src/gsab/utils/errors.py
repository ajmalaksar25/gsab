"""Translate Google API errors into friendly GSAB exceptions, with retry/backoff.

``execute()`` wraps a Google API request: it retries transient failures (429 and
5xx) with exponential backoff, then maps any remaining error to a GSAB exception
whose message tells the user — or an LLM agent — what to do next.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket

from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.errors import HttpError

from ..exceptions.custom_exceptions import (
    APIError,
    AuthError,
    GSABError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    ValidationError,
)
from ..exceptions.custom_exceptions import ConnectionError as GSABConnectionError

logger = logging.getLogger(__name__)

# Statuses worth retrying: rate limiting and transient server errors.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

# Transient transport failures worth retrying — a dropped connection or a timeout
# while waiting for data, not a permanent error.
_RETRYABLE_NETWORK = (ConnectionError, TimeoutError, socket.timeout, TransportError)


def error_for_status(status: int, detail: str) -> GSABError:
    """Map an HTTP status (from Sheets or gviz) to the closest GSAB exception."""
    low = detail.lower()
    if status == 401:
        return AuthError(
            f"Not authenticated with Google ({detail}). Run `gsab auth login` to sign in again."
        )
    if status == 403:
        if "quota" in low or "rate limit" in low or "ratelimit" in low:
            return QuotaExceededError(f"Google API quota exceeded ({detail}). Wait, then retry.")
        return PermissionDeniedError(
            f"Access denied ({detail}). Check this account can open the spreadsheet "
            "and that the needed scopes were granted at login."
        )
    if status == 404:
        return NotFoundError(
            f"Spreadsheet or tab not found ({detail}). Check the sheet id and tab name."
        )
    if status == 429:
        return QuotaExceededError(
            f"Rate limited by Google ({detail}). Retried with backoff — try again shortly."
        )
    if status == 400:
        return ValidationError(f"Google rejected the request ({detail}).")
    return APIError(f"Google Sheets API error {status or '?'}: {detail}")


def _status(error: HttpError) -> int:
    try:
        return int(error.resp.status)
    except (AttributeError, TypeError, ValueError):
        return 0


def _detail(error: HttpError) -> str:
    """Pull Google's human-readable message out of the JSON error body."""
    try:
        body = json.loads(error.content.decode("utf-8"))
        return body["error"]["message"]
    except (ValueError, KeyError, AttributeError, UnicodeDecodeError):
        return str(error)


def to_gsab_error(error: HttpError) -> GSABError:
    """Map a Google ``HttpError`` to the closest GSAB exception."""
    return error_for_status(_status(error), _detail(error))


async def _backoff(op: str, why: object, attempt: int, retries: int, base_delay: float) -> None:
    delay = base_delay * 2**attempt
    logger.warning(
        "Google API %s failed (%s); retry %d/%d in %.1fs", op, why, attempt + 1, retries, delay
    )
    await asyncio.sleep(delay)


async def execute(request, *, op: str = "request", retries: int = 5, base_delay: float = 0.5):
    """Run a Google API request, retrying transient errors with exponential backoff.

    Retries 429/5xx responses and transient network failures (dropped connection,
    timeout). Maps anything that finally fails to a friendly GSAB exception, and a
    failed token refresh to ``AuthError``.

    Args:
        request: a built Google API request (anything with ``.execute()``).
        op: short label for logs, e.g. ``"read"`` or ``"insert"``.
        retries: max retry attempts for transient failures.
        base_delay: first backoff delay in seconds (doubles each attempt).

    Returns:
        The request's parsed response.

    Raises:
        GSABError: a friendly, mapped exception on non-retryable or final failure.
    """
    for attempt in range(retries + 1):
        try:
            return request.execute()
        except HttpError as e:
            status = _status(e)
            if status in RETRYABLE_STATUSES and attempt < retries:
                await _backoff(op, status, attempt, retries, base_delay)
                continue
            raise to_gsab_error(e) from e
        except RefreshError as e:
            raise AuthError(
                f"Google session expired or was revoked ({e}). "
                "Run `gsab auth login` to sign in again."
            ) from e
        except _RETRYABLE_NETWORK as e:
            if attempt < retries:
                await _backoff(op, type(e).__name__, attempt, retries, base_delay)
                continue
            raise GSABConnectionError(
                f"Network error during {op} ({e}). Check your connection and try again."
            ) from e
