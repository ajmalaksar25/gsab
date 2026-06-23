"""Credential resolution for GSAB.

Auto-detect order (first match wins):
  1. Explicit service account  (arg / GSAB_SERVICE_ACCOUNT / GOOGLE_APPLICATION_CREDENTIALS)
  2. Cached user token         (saved by ``gsab auth login``)
  3. gcloud ADC                (``gcloud auth application-default login``)
  4. Interactive browser OAuth (login only)

Service accounts suit servers/CI; the cached-token + gcloud + browser tiers
cover a person signing in on their own machine.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Sequence

from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from platformdirs import user_config_dir

from ..exceptions.custom_exceptions import AuthError
from ..exceptions.custom_exceptions import ConnectionError as GSABConnectionError

# Easy mode (default): non-sensitive. GSAB only touches the sheets it creates or
# the user explicitly opens — no app-verification wall, no scary consent screen.
DEFAULT_SCOPES = ("https://www.googleapis.com/auth/drive.file",)

# DIY / "connect my existing sheets": broader, sensitive+restricted scopes. Opt-in.
FULL_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

ENV_SERVICE_ACCOUNT = "GSAB_SERVICE_ACCOUNT"
ENV_CLIENT_SECRETS = "GSAB_CLIENT_SECRETS"

CONFIG_DIR = Path(user_config_dir("gsab"))
TOKEN_PATH = CONFIG_DIR / "token.json"


def _scopes(scopes: Optional[Sequence[str]]) -> list:
    return list(scopes) if scopes else list(DEFAULT_SCOPES)


def _service_account_file(explicit: Optional[str] = None) -> Optional[str]:
    path = explicit or os.getenv(ENV_SERVICE_ACCOUNT) or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    return path if path and Path(path).exists() else None


def _bundled_client_secret() -> Optional[str]:
    """Path to the GSAB-shipped OAuth client, if this build includes one (easy mode)."""
    try:
        from importlib.resources import files

        p = files("gsab.auth").joinpath("client_secret.json")
        return str(p) if p.is_file() else None
    except Exception:
        return None


def _client_secrets(explicit: Optional[str] = None) -> Optional[str]:
    for cand in (explicit, os.getenv(ENV_CLIENT_SECRETS), str(CONFIG_DIR / "client_secret.json")):
        if cand and Path(cand).exists():
            return cand
    return _bundled_client_secret()


_KEYRING_SERVICE = "gsab"
_KEYRING_USER = "oauth-token"


def _keyring():
    """Return a usable keyring backend (OS keychain), or None to fall back to a file."""
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        if isinstance(keyring.get_keyring(), FailKeyring):
            return None
        return keyring
    except Exception:
        return None


def _save(creds: Credentials) -> None:
    """Store the token in the OS keychain when available, else a 0600 file."""
    data = creds.to_json()
    kr = _keyring()
    if kr:
        try:
            kr.set_password(_KEYRING_SERVICE, _KEYRING_USER, data)
            TOKEN_PATH.unlink(missing_ok=True)
            return
        except Exception:
            pass
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(data)
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass


def _read_token() -> Optional[str]:
    """Return the stored token JSON (keychain first, then file), or None."""
    kr = _keyring()
    if kr:
        try:
            data = kr.get_password(_KEYRING_SERVICE, _KEYRING_USER)
            if data:
                return data
        except Exception:
            pass
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text()
    return None


def _load_cached(scopes: Optional[Sequence[str]]) -> Optional[Credentials]:
    data = _read_token()
    if not data:
        return None
    creds = Credentials.from_authorized_user_info(json.loads(data), _scopes(scopes))
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise AuthError(
                "Your saved Google session has expired or was revoked. "
                "Run `gsab auth login` to sign in again."
            ) from e
        except TransportError as e:
            raise GSABConnectionError(
                f"Could not reach Google to refresh your session ({e}). Check your connection."
            ) from e
        _save(creds)
    return creds if creds and creds.valid else None


def _try_adc(scopes: Optional[Sequence[str]]) -> Optional[Credentials]:
    try:
        import google.auth

        creds, _ = google.auth.default(scopes=_scopes(scopes))
        return creds
    except Exception:
        return None


def resolve_credentials(
    scopes: Optional[Sequence[str]] = None,
    *,
    service_account_file: Optional[str] = None,
    interactive: bool = False,
) -> Credentials:
    """Resolve Google credentials from the best available source.

    Raises :class:`AuthError` with actionable guidance when nothing is found
    and ``interactive`` is False.
    """
    sa = _service_account_file(service_account_file)
    if sa:
        return service_account.Credentials.from_service_account_file(sa, scopes=_scopes(scopes))

    cached = _load_cached(scopes)
    if cached:
        return cached

    adc = _try_adc(scopes)
    if adc:
        return adc

    if interactive:
        return login(scopes)

    raise AuthError(
        "No Google credentials found. Do one of:\n"
        "  • run `gsab auth login` (browser sign-in), or\n"
        "  • run `gcloud auth application-default login`, or\n"
        f"  • set {ENV_SERVICE_ACCOUNT} to a service-account JSON file."
    )


def login(
    scopes: Optional[Sequence[str]] = None,
    *,
    client_secrets: Optional[str] = None,
    no_browser: bool = False,
) -> Credentials:
    """Run the interactive browser sign-in and cache the token for reuse."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets = _client_secrets(client_secrets)
    if not secrets:
        raise AuthError(
            "OAuth client secrets not found. Create a Desktop OAuth client in the "
            "Google Cloud Console, download the JSON, then either:\n"
            "  • pass --client-secrets PATH, or\n"
            f"  • set {ENV_CLIENT_SECRETS}, or\n"
            f"  • place it at {CONFIG_DIR / 'client_secret.json'}.\n"
            "Alternatively, skip this and use `gcloud auth application-default login`."
        )

    flow = InstalledAppFlow.from_client_secrets_file(secrets, _scopes(scopes))
    creds = flow.run_local_server(port=0, open_browser=not no_browser)
    _save(creds)
    return creds


def status(scopes: Optional[Sequence[str]] = None) -> dict:
    """Report available credential sources (no network calls beyond ADC lookup)."""
    token = _read_token()
    info = {
        "storage": "keyring" if _keyring() else "file",
        "token_cache": str(TOKEN_PATH),
        "logged_in": token is not None,
        "service_account": _service_account_file(),
        "client_secrets": _client_secrets(),
        "adc_available": _try_adc(scopes) is not None,
        "valid": False,
    }
    if token:
        try:
            creds = Credentials.from_authorized_user_info(json.loads(token), _scopes(scopes))
            info["valid"] = bool(creds and (creds.valid or creds.refresh_token))
        except Exception:
            info["valid"] = False
    return info


def logout() -> bool:
    """Delete the cached token from the keychain and/or file. True if anything was removed."""
    removed = False
    kr = _keyring()
    if kr:
        try:
            if kr.get_password(_KEYRING_SERVICE, _KEYRING_USER):
                kr.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
                removed = True
        except Exception:
            pass
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        removed = True
    return removed
