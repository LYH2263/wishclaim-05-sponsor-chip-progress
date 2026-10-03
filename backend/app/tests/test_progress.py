from app.modules.progress import effective_target, project, preview, decorate


def test_unclaimed_uses_live_target_claimed_uses_snapshot():
    assert effective_target("open", 100, 50) == 100
    assert effective_target("released", 100, 50) == 100
    assert effective_target("claimed", 100, 50) == 50
    assert effective_target("fulfilled", 100, 50) == 50


def test_snapshot_not_refreshed_when_target_edited_after_claim():
    # 认领后把 target 从 50 改成 999，快照仍为 50
    p = project(60, effective_target("claimed", target_amount=999, claimed_target_amount=50))
    assert p["target_amount"] == 50 and p["funded"] is True
    # 未认领愿望则跟随新目标
    p2 = project(60, effective_target("open", target_amount=999, claimed_target_amount=None))
    assert p2["target_amount"] == 999 and p2["funded"] is False and p2["gap"] == 939


def test_project_no_target():
    p = project(10, None)
    assert p == {"target_amount": None, "contributed": 10, "gap": None,
                 "funded": None, "ratio": None}


def test_project_gap_ratio_and_funded():
    p = project(30, 100)
    assert p["gap"] == 70 and p["funded"] is False and p["ratio"] == 0.3
    full = project(100, 100)
    assert full["gap"] == 0 and full["funded"] is True and full["ratio"] == 1.0
    over = project(120, 100)
    assert over["gap"] == 0 and over["funded"] is True and over["ratio"] == 1.0


def test_preview_does_not_mutate_totals():
    pv = preview(30, 100, 50)
    assert pv["contributed"] == 30          # 现有累计不变
    assert pv["projected_total"] == 80      # 假想累计
    assert pv["gap"] == 70 and pv["projected_gap"] == 20
    assert pv["would_reach"] is False
    hit = preview(80, 100, 20)
    assert hit["projected_gap"] == 0 and hit["would_reach"] is True


def test_preview_overpay_clamps_gap():
    pv = preview(90, 100, 50)
    assert pv["projected_total"] == 140 and pv["projected_gap"] == 0


def test_decorate_attaches_progress():
    w = {"id": 1, "status": "claimed", "target_amount": 100,
         "claimed_target_amount": 80}
    decorate(w, 80)
    assert w["progress"]["target_amount"] == 80
    assert w["progress"]["funded"] is True
