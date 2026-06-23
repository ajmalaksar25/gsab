"""OAuth client-secrets loading must tolerate a UTF-8 BOM (clean-install login bug)."""

import json

import pytest

from gsab.auth.resolver import _load_client_config
from gsab.exceptions import AuthError

CLIENT = {
    "installed": {
        "client_id": "x.apps.googleusercontent.com",
        "client_secret": "y",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def test_loads_plain_json(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(CLIENT), encoding="utf-8")
    assert _load_client_config(str(p)) == CLIENT


def test_loads_with_utf8_bom(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(CLIENT), encoding="utf-8-sig")  # prepends a BOM
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")  # confirm the BOM is there
    assert _load_client_config(str(p)) == CLIENT  # ...and is tolerated


def test_malformed_raises_friendly_autherror(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("not json at all", encoding="utf-8")
    with pytest.raises(AuthError):
        _load_client_config(str(p))


def test_missing_file_raises_friendly_autherror():
    with pytest.raises(AuthError):
        _load_client_config("/no/such/client_secret.json")
