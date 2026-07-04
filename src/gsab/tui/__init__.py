"""GSAB access-control TUI (optional ``tui`` extra).

Import stays light — ``textual`` is only pulled in when the app actually runs, so
``gsab.tui.model`` (the pure guardrail logic) is importable without the extra.
"""

from __future__ import annotations

from typing import Optional


def run(policy_path: Optional[str] = None) -> None:
    """Launch the access-control TUI (needs ``pip install "gsab[tui]"``)."""
    from .app import run as _run

    _run(policy_path)
