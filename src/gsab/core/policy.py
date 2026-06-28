"""AccessPolicy — client-side guardrails for what a SheetManager (and the MCP/TUI) may do.

Construct it in Python and pass it to ``SheetManager(..., policy=...)``; save/load it as a
small JSON profile to share the same config across the library, the MCP server and the TUI.
This is a guardrail layer for safety, control and visibility — NOT the security boundary
(that stays the OAuth scope, e.g. ``drive.file``). A determined caller of the raw library
can bypass it; Google still enforces the real permissions.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..exceptions.custom_exceptions import PolicyError, ValidationError

# Share roles in increasing privilege; used to cap share() at ``max_share_role``.
_ROLE_RANK = {"reader": 0, "commenter": 1, "writer": 2}
_ROLE_ALIASES = {
    "viewer": "reader",
    "view": "reader",
    "comment": "commenter",
    "editor": "writer",
    "edit": "writer",
}


def _norm_role(role: str) -> str:
    """Normalize a share role (aliasing the Sheets UI term 'editor' -> 'writer')."""
    normalized = _ROLE_ALIASES.get(role.lower(), role.lower())
    if normalized not in _ROLE_RANK:
        raise ValidationError(
            f"share role must be one of {', '.join(_ROLE_RANK)} "
            "('editor' is accepted as an alias for 'writer')."
        )
    return normalized


@dataclass
class AccessPolicy:
    """Guardrails for a ``SheetManager`` (and the MCP / TUI surfaces over it).

    Args:
        read_only: block every mutation (create, insert, update, upsert, delete, share).
        allowed_sheets: spreadsheet ids the policy permits operating on. ``None`` means
            "any the credential can reach" (the OAuth scope is the real floor); a list
            narrows further. A sheet created through this manager is always permitted.
        allow_share: whether public sharing is permitted at all.
        default_share_role: role used when ``share()`` is called without one.
        max_share_role: the highest role ``share()`` may grant (cap). Set to ``"reader"``
            to forbid public-edit; ``"writer"`` (default) allows it.
        confirm_destructive: require an explicit ``confirm=True`` for destructive ops
            (``delete``) instead of running them straight away.
        on_activity: optional callback invoked with an event dict after each operation
            (the feed the TUI / MCP-UI render). Never allowed to break an operation.
    """

    read_only: bool = False
    allowed_sheets: Optional[List[str]] = None
    allow_share: bool = True
    default_share_role: str = "reader"
    max_share_role: str = "writer"
    confirm_destructive: bool = False
    on_activity: Optional[Callable[[Dict[str, Any]], None]] = None

    def __post_init__(self) -> None:
        # Validate the role fields up front so a bad profile fails loudly at construction.
        _norm_role(self.default_share_role)
        _norm_role(self.max_share_role)

    # --- checks (raise PolicyError when an action is blocked) ----------------

    def ensure_writable(self, op: str) -> None:
        """Raise ``PolicyError`` if the policy is read-only."""
        if self.read_only:
            raise PolicyError(f"AccessPolicy is read-only — '{op}' is not allowed.")

    def ensure_sheet_allowed(self, sheet_id: str) -> None:
        """Raise ``PolicyError`` if ``sheet_id`` is outside an explicit allowlist."""
        if self.allowed_sheets is not None and sheet_id not in self.allowed_sheets:
            raise PolicyError(
                f"Sheet {sheet_id} is not in this AccessPolicy's allowed_sheets. "
                "Add it to allowed_sheets to operate on it."
            )

    def ensure_destructive_ok(self, op: str, confirm: bool) -> None:
        """Raise ``PolicyError`` if a destructive op needs confirmation and didn't get it."""
        if self.confirm_destructive and not confirm:
            raise PolicyError(
                f"'{op}' is destructive and this AccessPolicy requires confirmation — "
                "pass confirm=True (or confirm in the TUI / MCP) to proceed."
            )

    def resolve_share_role(self, role: Optional[str]) -> str:
        """Apply the default, normalize aliases, and cap at ``max_share_role``."""
        if not self.allow_share:
            raise PolicyError("Sharing is disabled by this AccessPolicy (allow_share=False).")
        chosen = _norm_role(role) if role else _norm_role(self.default_share_role)
        cap = _norm_role(self.max_share_role)
        if _ROLE_RANK[chosen] > _ROLE_RANK[cap]:
            raise PolicyError(
                f"share role '{chosen}' exceeds this AccessPolicy's max_share_role '{cap}'."
            )
        return chosen

    def emit(self, event: Dict[str, Any]) -> None:
        """Fire the ``on_activity`` hook for visibility; swallow any error it raises."""
        if self.on_activity:
            try:
                self.on_activity(event)
            except Exception:
                pass

    # --- the shareable profile file form -------------------------------------

    def save(self, path: str) -> None:
        """Write the policy to a JSON profile (the ``on_activity`` hook is not stored)."""
        data = {k: v for k, v in asdict(self).items() if k != "on_activity"}
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "AccessPolicy":
        """Read a policy from a JSON profile, ignoring unknown / non-serializable keys."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)} - {"on_activity"}
        return cls(**{k: v for k, v in raw.items() if k in known})
