"""Pure, UI-free logic behind the AccessPolicy TUI.

Kept free of any ``textual`` import so the offline test suite (and the 3.9 CI) can
exercise the guardrail decisions without the optional ``tui`` extra installed.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..core.policy import AccessPolicy
from ..exceptions import PolicyError

# The operations the probe can simulate, in a sensible menu order. Reads first so it is
# obvious that a read-only policy still lets them through.
OPERATIONS = [
    "read",
    "query",
    "insert",
    "upsert",
    "update",
    "delete",
    "share",
    "create_sheet",
]

# Ops that mutate — gated by ``read_only``. Mirrors ``ensure_writable`` in SheetManager.
WRITE_OPS = {"insert", "upsert", "update", "delete", "share", "create_sheet"}
# Ops gated by ``confirm_destructive`` (need ``confirm=True``).
DESTRUCTIVE_OPS = {"delete"}


def probe(
    policy: AccessPolicy,
    op: str,
    sheet_id: Optional[str] = None,
    *,
    confirm: bool = False,
    share_role: Optional[str] = None,
) -> Tuple[bool, str]:
    """Decide whether ``op`` would be allowed under ``policy`` — no network, no side effects.

    Runs the exact guardrail checks a ``SheetManager`` (and the MCP server) apply, in the
    same order, so the TUI shows the real answer.

    Args:
        policy: the AccessPolicy to test against.
        op: one of ``OPERATIONS``.
        sheet_id: the spreadsheet id the op would touch (ignored for ``create_sheet``,
            which always makes a fresh, allow-listed sheet).
        confirm: the ``confirm=True`` a destructive op would be called with.
        share_role: the role passed to ``share()`` (``None`` = the policy default).

    Returns:
        ``(allowed, detail)`` — ``detail`` is a short reason on allow, or the
        ``PolicyError`` message explaining the block.
    """
    op = op.lower()
    try:
        if op in WRITE_OPS:
            policy.ensure_writable(op)
        # The allowlist applies to any op bound to an existing sheet; a create makes a new
        # one that is exempt.
        if op != "create_sheet" and sheet_id:
            policy.ensure_sheet_allowed(sheet_id)
        if op in DESTRUCTIVE_OPS:
            policy.ensure_destructive_ok(op, confirm)
        if op == "share":
            role = policy.resolve_share_role(share_role)
            return True, f"allowed — shares as '{role}'"
        return True, "allowed"
    except PolicyError as e:
        return False, str(e)


def event_for(op: str, sheet_id: Optional[str], share_role: Optional[str]) -> Dict[str, Any]:
    """The activity event an allowed op would emit (what ``on_activity`` receives)."""
    event: Dict[str, Any] = {"op": op}
    if sheet_id:
        event["sheet_id"] = sheet_id
    if op == "share" and share_role:
        event["role"] = share_role
    return event


def format_event(event: Dict[str, Any]) -> str:
    """Render an ``on_activity`` event dict as one compact line for the feed."""
    op = event.get("op", "?")
    extras = [
        f"{k}={event[k]}"
        for k in ("sheet_id", "count", "role", "title", "url")
        if event.get(k) is not None
    ]
    return f"{op}" + (f"  ({', '.join(extras)})" if extras else "")
