"""Offline tests for the auth layer.

Cover the credential resolver (`resolve_credentials` / `status`) and the legacy
service-account `GoogleAuthenticator`, all without network or real credentials.
"""

import pytest

from gsab.auth import resolver
from gsab.auth.authenticator import AuthenticationError, GoogleAuthenticator
from gsab.auth.resolver import DEFAULT_SCOPES, FULL_SCOPES, resolve_credentials, status
from gsab.exceptions import AuthError, GSABError


def test_default_scopes_are_minimal_drive_file():
    # Easy mode ships the non-sensitive drive.file scope only; FULL_SCOPES is opt-in.
    assert DEFAULT_SCOPES == ("https://www.googleapis.com/auth/drive.file",)
    assert "https://www.googleapis.com/auth/spreadsheets" in FULL_SCOPES
    assert "https://www.googleapis.com/auth/drive" in FULL_SCOPES


def test_resolve_credentials_raises_autherror_when_nothing_available(monkeypatch):
    # No service account, no cached token, no ADC -> an actionable AuthError.
    monkeypatch.setattr(resolver, "_service_account_file", lambda explicit=None: None)
    monkeypatch.setattr(resolver, "_load_cached", lambda scopes: None)
    monkeypatch.setattr(resolver, "_try_adc", lambda scopes: None)
    with pytest.raises(AuthError) as exc:
        resolve_credentials()
    assert "gsab auth login" in str(exc.value)


def test_status_reports_logged_out_shape(monkeypatch):
    monkeypatch.setattr(resolver, "_read_token", lambda: None)
    monkeypatch.setattr(resolver, "_try_adc", lambda scopes: None)
    info = status()
    assert info["logged_in"] is False
    assert info["valid"] is False
    assert {"storage", "logged_in", "service_account", "client_secrets"} <= set(info)


def test_authentication_error_is_in_gsab_hierarchy():
    # The legacy authenticator's error must subclass GSABError like every other.
    assert issubclass(AuthenticationError, AuthError)
    assert issubclass(AuthenticationError, GSABError)


def test_google_authenticator_bad_path_raises_authentication_error():
    # A missing service-account file fails before any network call.
    with pytest.raises(AuthenticationError):
        GoogleAuthenticator("definitely-not-a-real-file.json").authenticate()
