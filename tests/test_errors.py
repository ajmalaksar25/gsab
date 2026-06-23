"""Offline tests for the error-mapping + retry layer (#7)."""

import json

import pytest
from googleapiclient.errors import HttpError

from gsab.exceptions import (
    APIError,
    AuthError,
    GSABError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    ValidationError,
)
from gsab.utils.errors import error_for_status, execute, to_gsab_error


class _Resp:
    def __init__(self, status):
        self.status = status
        self.reason = "test"


def _http_error(status, message="boom"):
    content = json.dumps({"error": {"message": message}}).encode("utf-8")
    return HttpError(_Resp(status), content)


@pytest.mark.parametrize(
    "status,exc",
    [
        (401, AuthError),
        (404, NotFoundError),
        (429, QuotaExceededError),
        (400, ValidationError),
        (500, APIError),
        (418, APIError),
    ],
)
def test_status_mapping(status, exc):
    err = error_for_status(status, "detail here")
    assert isinstance(err, exc)
    assert isinstance(err, GSABError)
    assert "detail here" in str(err)


def test_403_splits_quota_vs_permission():
    assert isinstance(error_for_status(403, "User rate limit exceeded"), QuotaExceededError)
    assert isinstance(
        error_for_status(403, "The caller does not have permission"), PermissionDeniedError
    )


def test_to_gsab_error_reads_google_message():
    err = to_gsab_error(_http_error(404, "Requested entity was not found."))
    assert isinstance(err, NotFoundError)
    assert "Requested entity was not found." in str(err)


class _FlakyRequest:
    """Fails with `status` for the first `fails` calls, then returns a result."""

    def __init__(self, fails, status):
        self.fails = fails
        self.status = status
        self.calls = 0

    def execute(self):
        self.calls += 1
        if self.calls <= self.fails:
            raise _http_error(self.status, "transient")
        return {"ok": True}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _instant(_seconds):
        return None

    monkeypatch.setattr("gsab.utils.errors.asyncio.sleep", _instant)


async def test_execute_retries_transient_then_succeeds():
    req = _FlakyRequest(fails=2, status=503)
    assert await execute(req, retries=3) == {"ok": True}
    assert req.calls == 3  # two failures + one success


async def test_execute_gives_up_after_retries():
    req = _FlakyRequest(fails=10, status=429)
    with pytest.raises(QuotaExceededError):
        await execute(req, retries=2)
    assert req.calls == 3  # initial + 2 retries


async def test_execute_does_not_retry_client_errors():
    req = _FlakyRequest(fails=10, status=404)
    with pytest.raises(NotFoundError):
        await execute(req, retries=5)
    assert req.calls == 1  # 404 is not retryable


class _NetworkRequest:
    """Raises a transport-level error (not HttpError) for the first `fails` calls."""

    def __init__(self, fails, exc):
        self.fails = fails
        self.exc = exc
        self.calls = 0

    def execute(self):
        self.calls += 1
        if self.calls <= self.fails:
            raise self.exc
        return {"ok": True}


async def test_execute_retries_network_drop_then_succeeds():
    req = _NetworkRequest(fails=2, exc=ConnectionError("connection reset"))
    assert await execute(req, retries=3) == {"ok": True}
    assert req.calls == 3


async def test_execute_maps_final_network_failure():
    from gsab.exceptions import ConnectionError as GSABConnectionError

    req = _NetworkRequest(fails=10, exc=TimeoutError("read timed out"))
    with pytest.raises(GSABConnectionError):
        await execute(req, retries=2)
    assert req.calls == 3


async def test_execute_maps_refresh_error_to_auth():
    from google.auth.exceptions import RefreshError

    req = _NetworkRequest(fails=1, exc=RefreshError("token revoked"))
    with pytest.raises(AuthError):
        await execute(req, retries=3)
    assert req.calls == 1  # refresh failure is not retryable
