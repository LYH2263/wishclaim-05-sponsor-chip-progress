import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="wishclaim_unit_"))

from app import seed
from app.db import connect
from app.modules import chipin_ledger as ledger
from app.modules import chipin_progress as progress
from app.modules import fulfill_gate


def setup_function(_):
    seed.init_db()
    c = connect()
    c.execute("DELETE FROM chipins")
    c.execute("DELETE FROM wishes")
    c.execute("INSERT INTO wishes(id,title,status,target_amount,pledged_total) VALUES (1,'g','open',100.0,0)")
    c.commit()
    c.close()


# ---------- ledger ----------

def test_amount_must_be_positive():
    for bad in (0, -1, -0.01, "5", None, float("nan"), float("inf"), True):
        assert ledger.validate_amount(bad)["ok"] is False
    for good in (0.01, 1, 999.99):
        assert ledger.validate_amount(good)["ok"] is True


def test_record_accumulates_in_ledger():
    c = connect()
    ledger.record(c, 1, "alice", 30.0, "2026-01-01T00:00:00+00:00")
    ledger.record(c, 1, "bob", 20.5, "2026-01-02T00:00:00+00:00")
    c.commit()
    assert ledger.total(c, 1) == 50.5
    assert ledger.count(c, 1) == 2
    rows = ledger.entries(c, 1)
    assert [r["backer"] for r in rows] == ["alice", "bob"]
    c.close()


def test_backer_name_trimmed_and_required():
    assert ledger.normalize_backer("  alice ") == "alice"
    assert ledger.normalize_backer("   ") == ""


# ---------- progress projection ----------

def test_project_totals_remaining_and_percent():
    p = progress.project(40.0, 100.0)
    assert p["pledged"] == 40.0 and p["remaining"] == 60.0
    assert p["percent"] == 40.0 and p["reached"] is False and p["has_target"] is True


def test_project_caps_percent_and_marks_reached():
    p = progress.project(120.0, 100.0)
    assert p["percent"] == 100.0 and p["remaining"] == 0.0 and p["reached"] is True


def test_project_without_target_has_no_goal():
    p = progress.project(50.0, None)
    assert p["has_target"] is False and p["remaining"] is None and p["reached"] is True


def test_preview_is_pure_and_temporary():
    before = progress.preview(40.0, 100.0, 30.0)
    assert before["pledged_now"] == 40.0
    assert before["pledged_after"] == 70.0
    assert before["remaining_after"] == 30.0
    assert before["reached_after"] is False and before["dry_run"] is True
    crossing = progress.preview(40.0, 100.0, 60.0)
    assert crossing["reached_after"] is True
    c = connect()
    # no ledger rows, no wish mutation as a result of preview
    assert ledger.total(c, 1) == 0
    c.close()


def test_effective_target_uses_snapshot_after_claim():
    assert progress.effective_target("open", 100.0, None) == 100.0
    assert progress.effective_target("claimed", 150.0, 100.0) == 100.0
    assert progress.effective_target("released", 150.0, None) == 150.0
    assert progress.effective_target("fulfilled", 150.0, 100.0) == 100.0


# ---------- fulfill gate ----------

def test_gate_blocks_until_goal_reached():
    short = progress.project(99.99, 100.0)
    assert fulfill_gate.can_fulfill("claimed", short)["reason"] == "goal_not_reached"
    ok = fulfill_gate.can_fulfill("claimed", progress.project(100.0, 100.0))
    assert ok["ok"] is True


def test_gate_no_target_always_passes_when_claimed():
    p = progress.project(0.0, None)
    assert fulfill_gate.can_fulfill("claimed", p)["ok"] is True
    assert fulfill_gate.can_fulfill("open", p)["reason"] == "need_claim"


def test_target_edit_only_unclaimed():
    assert fulfill_gate.target_editable("open")["ok"] is True
    assert fulfill_gate.target_editable("released")["ok"] is True
    assert fulfill_gate.target_editable("claimed")["reason"] == "target_locked_after_claim"
    assert fulfill_gate.target_editable("fulfilled")["reason"] == "target_locked_after_claim"


def test_validate_target():
    for bad in (0, -5, "100", float("nan")):
        assert fulfill_gate.validate_target(bad)["ok"] is False
    assert fulfill_gate.validate_target(None)["ok"] is True
    assert fulfill_gate.validate_target(100.0)["ok"] is True
