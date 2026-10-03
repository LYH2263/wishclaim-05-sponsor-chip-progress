import sqlite3
from app.modules.chipin import (
    add, create_table, total, totals_map, entries,
    validate_amount, normalize_sponsor,
)


def c():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_table(conn)
    return conn


def test_rejects_non_positive_amount():
    assert validate_amount(0)["reason"] == "amount_not_positive"
    assert validate_amount(-1)["reason"] == "amount_not_positive"
    assert validate_amount(-0.01)["reason"] == "amount_not_positive"


def test_rejects_bad_amount_types():
    for bad in ("10", None, [1], True, False, float("nan"), float("inf"), float("-inf")):
        assert validate_amount(bad)["ok"] is False, bad


def test_accepts_positive_numbers():
    assert validate_amount(1)["ok"]
    assert validate_amount(0.01)["ok"]
    assert validate_amount(999999)["ok"]


def test_ledger_accumulates_and_keeps_sponsors_separate():
    conn = c()
    at = "2026-10-03T00:00:00+00:00"
    add(conn, 1, normalize_sponsor(" alice "), 10, at)
    add(conn, 1, normalize_sponsor("bob"), 2.5, at)
    add(conn, 2, "carol", 7, at)
    assert total(conn, 1) == 12.5
    assert total(conn, 2) == 7.0
    assert total(conn, 99) == 0
    assert totals_map(conn) == {1: 12.5, 2: 7.0}
    rows = entries(conn, 1)
    assert [r["sponsor"] for r in rows] == ["alice", "bob"]
    assert [r["amount"] for r in rows] == [10.0, 2.5]


def test_sponsor_track_independent_from_claimer_name():
    # 同一名字可作为赞助人反复出现；账本不关心 claimer 轨
    conn = c()
    add(conn, 1, "alice", 3, "t1")
    add(conn, 1, "alice", 4, "t2")
    assert total(conn, 1) == 7
