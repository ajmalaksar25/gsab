"""Offline tests for the query layer (filter operators + gviz parsing)."""

import pytest

from gsab.core.query import build_gviz_url, parse_gviz_response
from gsab.core.sheet_manager import _match_op


def test_build_gviz_url():
    url = build_gviz_url("SHEET123", "SELECT A, B WHERE C > 5", sheet="users")
    assert url.startswith("https://docs.google.com/spreadsheets/d/SHEET123/gviz/tq?")
    assert "tqx=out%3Ajson" in url
    assert "sheet=users" in url
    assert "headers=1" in url


def test_parse_gviz_response():
    payload = (
        "/*O_o*/\ngoogle.visualization.Query.setResponse("
        '{"status":"ok","table":{'
        '"cols":[{"id":"A","label":"id"},{"id":"B","label":"plan"}],'
        '"rows":[{"c":[{"v":101.0},{"v":"pro"}]},{"c":[{"v":102.0},{"v":"free"}]}]'
        "}});"
    )
    rows = parse_gviz_response(payload)
    assert rows == [{"id": 101.0, "plan": "pro"}, {"id": 102.0, "plan": "free"}]


def test_parse_gviz_empty():
    payload = '/*O_o*/\nx({"table":{"cols":[{"id":"A","label":"id"}],"rows":[]}});'
    assert parse_gviz_response(payload) == []


def test_parse_gviz_bad():
    with pytest.raises(ValueError):
        parse_gviz_response("not a gviz response")


@pytest.mark.parametrize(
    "actual,op,target,expected",
    [
        (5, "$gt", 3, True),
        (5, "$gt", 8, False),
        (5, "$gte", 5, True),
        (2, "$lt", 5, True),
        (5, "$lte", 5, True),
        ("pro", "$eq", "pro", True),
        ("pro", "$ne", "free", True),
        ("pro", "$in", ["pro", "team"], True),
        ("free", "$nin", ["pro", "team"], True),
        ("ada@x.org", "$contains", "@", True),
        ("Ada", "$regex", "^A", True),
        (None, "$gt", 3, False),
        ("x", "$gt", 3, False),  # non-comparable types -> False, not a crash
    ],
)
def test_match_op(actual, op, target, expected):
    assert _match_op(actual, op, target) is expected


def test_match_op_unknown():
    with pytest.raises(ValueError):
        _match_op(1, "$wat", 1)
