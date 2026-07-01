"""Tests for the access-control TUI.

The guardrail-decision logic (``gsab.tui.model``) is tested offline with no ``textual``
dependency, so it runs everywhere including the 3.9 CI. The Textual app is driven through
a real headless pilot, but only when the optional ``tui`` extra is installed.
"""

import pytest

from gsab import AccessPolicy
from gsab.tui.model import OPERATIONS, event_for, format_event, probe

# --- pure guardrail logic (no textual) --------------------------------------


def test_probe_default_allows_everything():
    p = AccessPolicy()
    for op in OPERATIONS:
        allowed, _ = probe(p, op, "SHEET")
        assert allowed, op


def test_probe_read_only_blocks_writes_but_allows_reads():
    p = AccessPolicy(read_only=True)
    assert probe(p, "read", "S")[0] is True
    assert probe(p, "query", "S")[0] is True
    for op in ("insert", "update", "upsert", "delete", "share", "create_sheet"):
        allowed, detail = probe(p, op, "S")
        assert not allowed and "read-only" in detail


def test_probe_allowlist_gates_existing_sheets_but_exempts_create():
    p = AccessPolicy(allowed_sheets=["OK"])
    assert probe(p, "read", "OK")[0] is True
    blocked, detail = probe(p, "read", "NOPE")
    assert not blocked and "allowed_sheets" in detail
    # create_sheet makes a fresh sheet -> never gated by the allowlist
    assert probe(p, "create_sheet", "NOPE")[0] is True


def test_probe_confirm_destructive():
    p = AccessPolicy(confirm_destructive=True)
    blocked, detail = probe(p, "delete", "S", confirm=False)
    assert not blocked and "confirm" in detail
    assert probe(p, "delete", "S", confirm=True)[0] is True


def test_probe_share_role_cap_and_default():
    p = AccessPolicy(max_share_role="reader")
    ok, detail = probe(p, "share", "S", share_role="reader")
    assert ok and "reader" in detail
    blocked, detail = probe(p, "share", "S", share_role="writer")
    assert not blocked and "max_share_role" in detail
    # editor alias resolves to writer, so it is also capped out
    assert probe(p, "share", "S", share_role="editor")[0] is False


def test_probe_allow_share_false():
    blocked, detail = probe(AccessPolicy(allow_share=False), "share", "S")
    assert not blocked and "disabled" in detail


def test_event_for_and_format_event():
    assert event_for("read", "S", None) == {"op": "read", "sheet_id": "S"}
    assert event_for("share", "S", "writer") == {"op": "share", "sheet_id": "S", "role": "writer"}
    assert event_for("create_sheet", None, None) == {"op": "create_sheet"}
    assert format_event({"op": "create_sheet"}) == "create_sheet"
    line = format_event({"op": "read", "sheet_id": "S", "count": 3})
    assert line == "read  (sheet_id=S, count=3)"


# --- the Textual app, driven headless (skipped without the `tui` extra) ------


async def test_app_probe_edit_and_persist(tmp_path):
    pytest.importorskip("textual")
    from textual.widgets import Input, Select, Switch

    from gsab.tui.app import PolicyConsole

    app = PolicyConsole()
    # A roomy headless screen so every control is on-screen for pilot.click().
    async with app.run_test(size=(160, 60)) as pilot:
        # Toggle read-only via the real switch, then probe.
        app.query_one("#read_only", Switch).value = True
        await pilot.pause()
        assert app.policy.read_only is True

        feed_before = len(app.query_one("#feed").lines)
        app.query_one("#op", Select).value = "insert"
        await pilot.pause()
        await pilot.click("#check")  # insert is blocked under read-only
        await pilot.pause()
        assert len(app.query_one("#feed").lines) > feed_before  # a blocked line was written

        # Build an allowlist through the UI.
        app.query_one("#allowlist_enabled", Switch).value = True
        app.query_one("#new_sheet", Input).value = "SHEET1"
        await pilot.pause()
        await pilot.click("#add_sheet")
        await pilot.pause()
        assert app.policy.allowed_sheets == ["SHEET1"]

        # Save the profile, then reload it independently.
        path = str(tmp_path / "pol.json")
        app.query_one("#profile_path", Input).value = path
        await pilot.pause()
        await pilot.click("#save")
        await pilot.pause()

    reloaded = AccessPolicy.load(path)
    assert reloaded.read_only is True
    assert reloaded.allowed_sheets == ["SHEET1"]
    assert reloaded.on_activity is None


async def test_app_blank_share_role_and_alias_profile(tmp_path):
    pytest.importorskip("textual")
    from textual.widgets import Select

    from gsab.tui.app import PolicyConsole

    # A profile written by an older gsab may store a raw role alias ("editor"); loading it
    # must normalize to a value the role Select accepts, not crash at mount.
    path = tmp_path / "aliased.json"
    path.write_text('{"default_share_role": "editor"}', encoding="utf-8")

    app = PolicyConsole(str(path))
    async with app.run_test(size=(160, 60)) as pilot:
        assert app.policy.default_share_role == "writer"  # alias canonicalized on load
        # Probe `share` with the role Select left blank (Select.NULL) must not tear the app
        # down — it should resolve to the policy default and be allowed.
        app.query_one("#op", Select).value = "share"
        await pilot.pause()
        await pilot.click("#check")
        await pilot.pause()
        assert app.is_running  # still alive: no uncaught ValidationError
