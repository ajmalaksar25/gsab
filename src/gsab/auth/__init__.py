"""Authentication for GSAB.

`resolve_credentials` auto-detects the best available credential source;
`login`/`logout`/`status` manage the interactive browser sign-in.
"""

from .authenticator import GoogleAuthenticator  # back-compat (service account)
from .resolver import (
    CONFIG_DIR,
    DEFAULT_SCOPES,
    FULL_SCOPES,
    TOKEN_PATH,
    login,
    logout,
    resolve_credentials,
    status,
)

__all__ = [
    "resolve_credentials",
    "login",
    "logout",
    "status",
    "DEFAULT_SCOPES",
    "FULL_SCOPES",
    "TOKEN_PATH",
    "CONFIG_DIR",
    "GoogleAuthenticator",
]
