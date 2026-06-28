"""A quiet, non-blocking "a newer gsab is out" notice for the CLI.

Checks PyPI for the latest version at most once a day (cached in the config dir),
prints a one-line notice to stderr if the installed version is behind, and never
raises or blocks a command. Opt out with ``GSAB_NO_UPDATE_CHECK=1``.
"""

from __future__ import annotations  # so `str | None` parses on Python 3.9

import json
import os
import sys
import time
import urllib.request

from ..auth.resolver import CONFIG_DIR

_CACHE = CONFIG_DIR / "update_check.json"
_INTERVAL = 86400  # seconds — check PyPI at most once a day
_PYPI = "https://pypi.org/pypi/gsab/json"
_TIMEOUT = 1.5


def _current() -> str:
    from .. import __version__

    return __version__


def _parse(v: str) -> tuple:
    """Leading-numeric tuple of a version, e.g. '0.7.1' -> (0, 7, 1)."""
    out = []
    for part in (v or "").split("."):
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        out.append(int(digits) if digits else 0)
    return tuple(out[:3])


def _newer(latest: str, current: str) -> bool:
    try:
        return _parse(latest) > _parse(current)
    except Exception:
        return False


def _read_cache() -> dict:
    try:
        return json.loads(_CACHE.read_text())
    except Exception:
        return {}


def _write_cache(latest: str) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps({"checked": time.time(), "latest": latest or ""}))
    except Exception:
        pass


def _fetch_latest() -> str:
    req = urllib.request.Request(_PYPI, headers={"User-Agent": "gsab-update-check"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310  # nosec B310
        return json.loads(r.read())["info"]["version"]


def latest_version() -> str | None:
    """Latest gsab version on PyPI, cached once/day. None on opt-out or any error."""
    if os.getenv("GSAB_NO_UPDATE_CHECK") not in (None, "", "0"):
        return None
    cache = _read_cache()
    if cache.get("latest") and (time.time() - cache.get("checked", 0)) < _INTERVAL:
        return cache["latest"]
    try:
        latest = _fetch_latest()
    except Exception:
        # Remember we tried (keep the old value) so we don't hammer PyPI when offline.
        _write_cache(cache.get("latest", ""))
        return cache.get("latest") or None
    _write_cache(latest)
    return latest


def notify_if_outdated(stream=None) -> None:
    """Print a one-line upgrade notice to stderr if a newer gsab exists. Never raises."""
    try:
        latest, current = latest_version(), _current()
        if latest and current and _newer(latest, current):
            print(
                f"A new gsab is available: {current} -> {latest}. "
                "Upgrade with `pip install -U gsab`.",
                file=stream or sys.stderr,
            )
    except Exception:
        pass
