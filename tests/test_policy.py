"""Unit tests for AccessPolicy guardrails (offline, no network)."""

import pytest

from gsab import AccessPolicy
from gsab.exceptions import PolicyError, ValidationError


def test_default_policy_is_permissive():
    p = AccessPolicy()
    p.ensure_writable("insert")  # no raise
    p.ensure_sheet_allowed("ANY")  # no allowlist -> no raise
    assert p.resolve_share_role(None) == "reader"


def test_read_only_blocks_mutations():
    with pytest.raises(PolicyError):
        AccessPolicy(read_only=True).ensure_writable("insert")


def test_allowed_sheets_gates_ids():
    p = AccessPolicy(allowed_sheets=["A", "B"])
    p.ensure_sheet_allowed("A")  # ok
    with pytest.raises(PolicyError):
        p.ensure_sheet_allowed("C")


def test_resolve_share_role_alias_and_default():
    p = AccessPolicy()
    assert p.resolve_share_role("editor") == "writer"
    assert p.resolve_share_role("comment") == "commenter"
    assert p.resolve_share_role(None) == "reader"


def test_max_share_role_caps():
    p = AccessPolicy(max_share_role="reader")
    assert p.resolve_share_role("reader") == "reader"
    with pytest.raises(PolicyError):
        p.resolve_share_role("writer")


def test_allow_share_false_blocks():
    with pytest.raises(PolicyError):
        AccessPolicy(allow_share=False).resolve_share_role("reader")


def test_bad_role_is_validation_error():
    with pytest.raises(ValidationError):
        AccessPolicy().resolve_share_role("owner")


def test_bad_role_field_rejected_at_construction():
    with pytest.raises(ValidationError):
        AccessPolicy(default_share_role="owner")


def test_role_aliases_canonicalized_at_construction():
    # Aliases are stored canonically so save/load and the TUI's role selects only ever
    # see reader/commenter/writer.
    p = AccessPolicy(default_share_role="editor", max_share_role="edit")
    assert p.default_share_role == "writer"
    assert p.max_share_role == "writer"


def test_load_canonicalizes_alias_roles(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(
        '{"default_share_role": "viewer", "max_share_role": "comment"}', encoding="utf-8"
    )
    p = AccessPolicy.load(str(path))
    assert p.default_share_role == "reader"
    assert p.max_share_role == "commenter"


def test_confirm_destructive_requires_confirm():
    p = AccessPolicy(confirm_destructive=True)
    with pytest.raises(PolicyError):
        p.ensure_destructive_ok("delete", confirm=False)
    p.ensure_destructive_ok("delete", confirm=True)  # ok


def test_on_activity_hook_fires_and_swallows_errors():
    events = []
    AccessPolicy(on_activity=events.append).emit({"op": "read"})
    assert events == [{"op": "read"}]

    def boom_hook(event):
        raise RuntimeError("hook failure must not propagate")

    AccessPolicy(on_activity=boom_hook).emit({"op": "read"})  # no raise


def test_save_load_round_trip(tmp_path):
    path = str(tmp_path / "policy.json")
    AccessPolicy(read_only=True, allowed_sheets=["A"], max_share_role="reader").save(path)
    loaded = AccessPolicy.load(path)
    assert loaded.read_only is True
    assert loaded.allowed_sheets == ["A"]
    assert loaded.max_share_role == "reader"
    assert loaded.on_activity is None


def test_load_ignores_unknown_keys(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text('{"read_only": true, "bogus": 1}', encoding="utf-8")
    assert AccessPolicy.load(str(path)).read_only is True


def test_save_does_not_copy_the_activity_hook(tmp_path):
    # on_activity may be a bound method of an object that can't be deep-copied (e.g. the
    # TUI app). save() must serialize the JSON fields without touching the hook.
    class Sink:
        def __deepcopy__(self, memo):  # pragma: no cover - only reached on regression
            raise RuntimeError("the activity hook must not be deep-copied on save")

        def __call__(self, event):
            pass

    path = str(tmp_path / "policy.json")
    AccessPolicy(read_only=True, allowed_sheets=["A"], on_activity=Sink()).save(path)
    loaded = AccessPolicy.load(path)
    assert loaded.read_only is True and loaded.allowed_sheets == ["A"]
