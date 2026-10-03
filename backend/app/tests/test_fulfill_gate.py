from app.modules.fulfill_gate import can_fulfill


def test_requires_claimed_status():
    assert can_fulfill("open", 100, 100)["reason"] == "need_claim"
    assert can_fulfill("fulfilled", 100, 100)["reason"] == "need_claim"
    assert can_fulfill("released", None, 0)["reason"] == "need_claim"


def test_target_unset_fulfills_with_claimed():
    assert can_fulfill("claimed", None, 0)["ok"] is True


def test_unfunded_blocked_and_stays_claimed():
    r = can_fulfill("claimed", 100, 99.99)
    assert r["ok"] is False and r["reason"] == "target_not_reached"


def test_funded_passes_gate():
    assert can_fulfill("claimed", 100, 100)["ok"] is True
    assert can_fulfill("claimed", 100, 130)["ok"] is True


def test_zero_target_treated_as_funded():
    assert can_fulfill("claimed", 0, 0)["ok"] is True
