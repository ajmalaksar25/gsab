"""Offline tests for the update-available notice and the keyring opt-out."""

import io
import time

from gsab.utils import update_check as uc


def test_newer_compares_versions():
    assert uc._newer("0.7.1", "0.7.0")
    assert uc._newer("1.0.0", "0.9.9")
    assert not uc._newer("0.7.0", "0.7.0")
    assert not uc._newer("0.6.9", "0.7.0")


def test_latest_version_opt_out(monkeypatch):
    monkeypatch.setenv("GSAB_NO_UPDATE_CHECK", "1")
    assert uc.latest_version() is None


def test_latest_version_uses_fresh_cache_without_network(monkeypatch):
    monkeypatch.delenv("GSAB_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(uc, "_read_cache", lambda: {"latest": "9.9.9", "checked": time.time()})
    calls = []
    monkeypatch.setattr(uc, "_fetch_latest", lambda: calls.append(1) or "0.0.0")
    assert uc.latest_version() == "9.9.9"
    assert calls == []  # fresh cache → no network call


def test_latest_version_fetches_when_stale(monkeypatch):
    monkeypatch.delenv("GSAB_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(uc, "_read_cache", lambda: {})
    monkeypatch.setattr(uc, "_write_cache", lambda v: None)
    monkeypatch.setattr(uc, "_fetch_latest", lambda: "1.2.3")
    assert uc.latest_version() == "1.2.3"


def test_latest_version_swallows_fetch_error(monkeypatch):
    monkeypatch.delenv("GSAB_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(uc, "_read_cache", lambda: {})
    monkeypatch.setattr(uc, "_write_cache", lambda v: None)

    def boom():
        raise RuntimeError("offline")

    monkeypatch.setattr(uc, "_fetch_latest", boom)
    assert uc.latest_version() is None  # error swallowed, never raises


def test_notify_prints_when_outdated(monkeypatch):
    monkeypatch.setattr(uc, "latest_version", lambda: "9.9.9")
    monkeypatch.setattr(uc, "_current", lambda: "0.7.1")
    buf = io.StringIO()
    uc.notify_if_outdated(stream=buf)
    assert "9.9.9" in buf.getvalue() and "pip install -U gsab" in buf.getvalue()


def test_notify_silent_when_current(monkeypatch):
    monkeypatch.setattr(uc, "latest_version", lambda: "0.7.1")
    monkeypatch.setattr(uc, "_current", lambda: "0.7.1")
    buf = io.StringIO()
    uc.notify_if_outdated(stream=buf)
    assert buf.getvalue() == ""


def test_keyring_opt_out(monkeypatch):
    from gsab.auth import resolver

    monkeypatch.setenv("GSAB_NO_KEYRING", "1")
    assert resolver._keyring() is None
