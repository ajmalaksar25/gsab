"""The GSAB access-control TUI — a terminal cockpit over ``AccessPolicy``.

Launch with ``gsab tui`` (needs the ``tui`` extra). Edit a policy, probe what it would
allow or block, save it as a JSON profile (the same profile ``gsab mcp --policy`` reads),
and watch a live feed of the ``on_activity`` events any op emits.

The policy on screen IS a real ``AccessPolicy`` object — its ``on_activity`` is wired to
the feed, so a ``SheetManager(..., policy=console.policy)`` sharing it streams here too.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Select,
    Switch,
)

from ..core.policy import AccessPolicy
from ..exceptions import GSABError
from .model import OPERATIONS, event_for, format_event, probe

_ROLES = [("reader", "reader"), ("commenter", "commenter"), ("writer", "writer")]


class ActivityLogged(Message):
    """One line for the activity feed (thread-safe hand-off from ``on_activity``)."""

    def __init__(self, line: str, *, blocked: bool = False) -> None:
        self.line = line
        self.blocked = blocked
        super().__init__()


class PolicyConsole(App):
    """Edit an AccessPolicy, probe it, and watch its activity feed."""

    TITLE = "GSAB — access control"
    CSS = """
    #body { height: 1fr; }
    #policy-pane { width: 42%; border-right: solid $panel; padding: 0 1; }
    #right-pane { width: 1fr; }
    #probe { height: auto; border-bottom: solid $panel; padding: 0 1; }
    #feed { height: 1fr; padding: 0 1; }
    .h { text-style: bold; color: $accent; padding: 1 0 0 0; }
    .row { height: auto; align: left middle; }
    .row Label { width: 24; }
    Select { width: 1fr; }
    Input { width: 1fr; }
    #allowlist { height: 8; border: solid $panel; }
    """
    BINDINGS = [("ctrl+s", "save", "Save profile"), ("q", "quit", "Quit")]

    def __init__(self, policy_path: Optional[str] = None) -> None:
        super().__init__()
        self.policy_path = policy_path
        self.policy = AccessPolicy.load(policy_path) if policy_path else AccessPolicy()
        # In-memory source of truth for the allowlist (avoids reading deferred widgets).
        self._sheets: List[str] = list(self.policy.allowed_sheets or [])

    # --- layout --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with VerticalScroll(id="policy-pane"):
                yield Label("Access policy", classes="h")
                yield from self._switch_row("Read-only (block writes)", "read_only")
                yield from self._switch_row("Allow public sharing", "allow_share")
                yield from self._switch_row("Confirm destructive ops", "confirm_destructive")
                with Horizontal(classes="row"):
                    yield Label("Default share role")
                    yield Select(
                        _ROLES,
                        value=self.policy.default_share_role,
                        allow_blank=False,
                        id="default_share_role",
                    )
                with Horizontal(classes="row"):
                    yield Label("Max share role")
                    yield Select(
                        _ROLES,
                        value=self.policy.max_share_role,
                        allow_blank=False,
                        id="max_share_role",
                    )

                yield Label("Allowed-sheets allowlist", classes="h")
                yield from self._switch_row(
                    "Restrict to an allowlist",
                    "allowlist_enabled",
                    value=self.policy.allowed_sheets is not None,
                )
                with Horizontal(classes="row"):
                    yield Input(placeholder="spreadsheet id", id="new_sheet")
                    yield Button("Add", id="add_sheet", variant="primary")
                yield ListView(*[ListItem(Label(s)) for s in self._sheets], id="allowlist")
                yield Button("Remove selected", id="remove_sheet")

                yield Label("Profile", classes="h")
                with Horizontal(classes="row"):
                    yield Input(
                        value=self.policy_path or "gsab-policy.json",
                        placeholder="path.json",
                        id="profile_path",
                    )
                with Horizontal(classes="row"):
                    yield Button("Save", id="save", variant="success")
                    yield Button("Load", id="load")

            with Vertical(id="right-pane"):
                with VerticalScroll(id="probe"):
                    yield Label("Probe — would this be allowed?", classes="h")
                    with Horizontal(classes="row"):
                        yield Label("Operation")
                        yield Select(
                            [(o, o) for o in OPERATIONS],
                            value="read",
                            allow_blank=False,
                            id="op",
                        )
                    with Horizontal(classes="row"):
                        yield Label("Sheet id")
                        yield Input(placeholder="(blank = a new/created sheet)", id="probe_sheet")
                    with Horizontal(classes="row"):
                        yield Label("Share role")
                        yield Select(_ROLES, prompt="(policy default)", id="probe_role")
                    yield from self._switch_row("Pass confirm=True", "probe_confirm")
                    yield Button("Check", id="check", variant="primary")
                yield Label("Activity feed", classes="h")
                yield RichLog(id="feed", markup=True, wrap=True, highlight=False)
        yield Footer()

    def _switch_row(self, label: str, wid: str, *, value: Optional[bool] = None) -> ComposeResult:
        if value is None:
            value = bool(getattr(self.policy, wid, False))
        with Horizontal(classes="row"):
            yield Label(label)
            yield Switch(value=value, id=wid)

    def on_mount(self) -> None:
        # Wire the live feed: every emit() on this policy lands in the RichLog.
        self.policy.on_activity = self._emit_to_feed
        self._log("[dim]policy loaded — edit it, probe it, watch ops here[/dim]")

    # --- feed plumbing (post_message is thread-safe, so a worker SheetManager is fine) ---

    def _emit_to_feed(self, event: Dict[str, Any]) -> None:
        try:
            self.post_message(ActivityLogged(format_event(event)))
        except Exception:
            pass

    @on(ActivityLogged)
    def _write_feed(self, msg: ActivityLogged) -> None:
        mark = "[red]✗ blocked[/red]" if msg.blocked else "[green]✓[/green]"
        self.query_one("#feed", RichLog).write(f"{mark} {msg.line}")

    def _log(self, line: str) -> None:
        self.query_one("#feed", RichLog).write(line)

    # --- policy edits --------------------------------------------------------

    @on(Switch.Changed, "#read_only")
    def _e_read_only(self, e: Switch.Changed) -> None:
        self.policy.read_only = e.value

    @on(Switch.Changed, "#allow_share")
    def _e_allow_share(self, e: Switch.Changed) -> None:
        self.policy.allow_share = e.value

    @on(Switch.Changed, "#confirm_destructive")
    def _e_confirm_destructive(self, e: Switch.Changed) -> None:
        self.policy.confirm_destructive = e.value

    @on(Switch.Changed, "#allowlist_enabled")
    def _e_allowlist(self, e: Switch.Changed) -> None:
        self.policy.allowed_sheets = list(self._sheets) if e.value else None

    @on(Select.Changed, "#default_share_role")
    def _e_default_role(self, e: Select.Changed) -> None:
        if e.value is not Select.NULL:
            self.policy.default_share_role = str(e.value)

    @on(Select.Changed, "#max_share_role")
    def _e_max_role(self, e: Select.Changed) -> None:
        if e.value is not Select.NULL:
            self.policy.max_share_role = str(e.value)

    # --- allowlist -----------------------------------------------------------

    def _sync_allowlist(self) -> None:
        if self.query_one("#allowlist_enabled", Switch).value:
            self.policy.allowed_sheets = list(self._sheets)

    def _render_allowlist(self) -> None:
        lv = self.query_one("#allowlist", ListView)
        lv.clear()
        for s in self._sheets:
            lv.append(ListItem(Label(s)))

    @on(Button.Pressed, "#add_sheet")
    def _add_sheet(self) -> None:
        box = self.query_one("#new_sheet", Input)
        sid = box.value.strip()
        if not sid or sid in self._sheets:
            box.value = ""
            return
        self._sheets.append(sid)
        box.value = ""
        self._render_allowlist()
        self._sync_allowlist()

    @on(Button.Pressed, "#remove_sheet")
    def _remove_sheet(self) -> None:
        idx = self.query_one("#allowlist", ListView).index
        if idx is not None and 0 <= idx < len(self._sheets):
            self._sheets.pop(idx)
            self._render_allowlist()
            self._sync_allowlist()

    # --- save / load ---------------------------------------------------------

    def action_save(self) -> None:
        self._save()

    @on(Button.Pressed, "#save")
    def _save(self) -> None:
        path = self.query_one("#profile_path", Input).value.strip() or "gsab-policy.json"
        try:
            self._sync_allowlist()
            self.policy.save(path)
            self.policy_path = path
            self.notify(f"saved policy → {path}")
        except OSError as e:
            self.notify(f"could not save: {e}", severity="error")

    @on(Button.Pressed, "#load")
    def _load(self) -> None:
        path = self.query_one("#profile_path", Input).value.strip()
        try:
            self.policy = AccessPolicy.load(path)
        except (OSError, ValueError, GSABError) as e:
            self.notify(f"could not load {path}: {e}", severity="error")
            return
        self.policy.on_activity = self._emit_to_feed
        self.policy_path = path
        self._sheets = list(self.policy.allowed_sheets or [])
        self._refresh_from_policy()
        self.notify(f"loaded policy ← {path}")

    def _refresh_from_policy(self) -> None:
        p = self.policy
        self.query_one("#read_only", Switch).value = p.read_only
        self.query_one("#allow_share", Switch).value = p.allow_share
        self.query_one("#confirm_destructive", Switch).value = p.confirm_destructive
        self.query_one("#default_share_role", Select).value = p.default_share_role
        self.query_one("#max_share_role", Select).value = p.max_share_role
        self.query_one("#allowlist_enabled", Switch).value = p.allowed_sheets is not None
        self._render_allowlist()

    # --- probe ---------------------------------------------------------------

    @on(Button.Pressed, "#check")
    def _check(self) -> None:
        op = str(self.query_one("#op", Select).value)
        sheet_id = self.query_one("#probe_sheet", Input).value.strip() or None
        confirm = self.query_one("#probe_confirm", Switch).value
        rv = self.query_one("#probe_role", Select).value
        role = None if rv is Select.NULL else str(rv)
        try:
            allowed, detail = probe(self.policy, op, sheet_id, confirm=confirm, share_role=role)
        except GSABError as e:  # a probe must never tear the UI down
            self.post_message(ActivityLogged(f"{op} {sheet_id or ''} — {e}", blocked=True))
            self.notify(str(e), severity="error")
            return
        if allowed:
            # Fire the real emit path so the feed shows exactly what on_activity would get.
            self.policy.emit(event_for(op, sheet_id, role))
            self.notify(detail)
        else:
            self.post_message(ActivityLogged(f"{op} {sheet_id or ''} — {detail}", blocked=True))
            self.notify(detail, severity="error")


def run(policy_path: Optional[str] = None) -> None:
    """Launch the TUI (blocks until the user quits)."""
    PolicyConsole(policy_path).run()
