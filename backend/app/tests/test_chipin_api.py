from app.tests.conftest import client  # noqa: F401


def create(client, **kw):
    body = {"title": "g", "note": "", **kw}
    return client.post("/api/wishes", json=body).json()["id"]


def chip(client, wid, backer, amount, route="confirm"):
    return client.post(f"/api/wishes/{wid}/chipin/{route}", json={"backer": backer, "amount": amount})


# ---------- target ----------

def test_create_with_target_rejects_non_positive(client):
    assert client.post("/api/wishes", json={"title": "g", "target_amount": 0}).status_code == 400
    assert client.post("/api/wishes", json={"title": "g", "target_amount": -3}).status_code == 400


def test_target_change_only_unclaimed(client):
    wid = create(client, target_amount=100.0)
    r = client.patch(f"/api/wishes/{wid}/target", json={"target_amount": 200.0})
    assert r.status_code == 200 and r.json()["progress"]["target"] == 200.0

    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "ann"})
    # claimed wish: edit rejected, snapshot stays at 200
    r = client.patch(f"/api/wishes/{wid}/target", json={"target_amount": 999.0})
    assert r.status_code == 409
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["target_snapshot"] == 200.0 and g["progress"]["target"] == 200.0


def test_snapshot_not_backfilled_and_release_clears_it(client):
    wid = create(client, target_amount=100.0)
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "ann"})
    # editing underlying target while claimed has no effect on the snapshot
    from app.db import connect
    c = connect(); c.execute("UPDATE wishes SET target_amount=500 WHERE id=?", (wid,)); c.commit(); c.close()
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["progress"]["target"] == 100.0

    client.post(f"/api/wishes/{wid}/release")
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["target_snapshot"] is None and g["progress"]["target"] == 500.0


# ---------- preview / confirm ----------

def test_preview_does_not_write(client):
    wid = create(client, target_amount=100.0)
    r = chip(client, wid, "bob", 30, "preview")
    assert r.status_code == 200
    p = r.json()
    assert p["pledged_now"] == 0.0 and p["pledged_after"] == 30.0
    assert p["remaining_after"] == 70.0 and p["percent_after"] == 30.0
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["progress"]["pledged"] == 0.0 and g["chipin_count"] == 0
    assert g["chipins"] == []


def test_confirm_accumulates_and_projects(client):
    wid = create(client, target_amount=100.0)
    r = chip(client, wid, "bob", 30.1)
    assert r.status_code == 200
    assert r.json()["progress"]["pledged"] == 30.1
    r = chip(client, wid, "carol", 69.9)
    p = r.json()["progress"]
    assert p["pledged"] == 100.0 and p["remaining"] == 0.0 and p["reached"] is True


def test_chipin_rejects_non_positive_amount(client):
    wid = create(client, target_amount=100.0)
    for bad in (0, -10):
        assert chip(client, wid, "bob", bad, "preview").status_code == 400
        assert chip(client, wid, "bob", bad).status_code == 400
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["chipin_count"] == 0


def test_chipin_rejects_blank_backer_and_fulfilled_wish(client):
    wid = create(client, target_amount=100.0)
    assert client.post(f"/api/wishes/{wid}/chipin/confirm",
                       json={"backer": "  ", "amount": 5}).status_code == 400
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "ann"})
    chip(client, wid, "x", 100)
    client.post(f"/api/wishes/{wid}/fulfill")
    for route in ("preview", "confirm"):
        assert chip(client, wid, "y", 1, route).status_code == 409
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["chipin_count"] == 1  # the rejected late chip-in was not recorded


# ---------- fulfill gate end to end ----------

def test_fulfill_blocked_keeps_claimed(client):
    wid = create(client, target_amount=100.0)
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "ann"})
    chip(client, wid, "bob", 99.99)
    r = client.post(f"/api/wishes/{wid}/fulfill")
    assert r.status_code == 409 and r.json()["detail"] == "goal_not_reached"
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["status"] == "claimed" and g["claimer"] == "ann" and g["expires_at"] is not None


def test_fulfill_allowed_when_reached_and_snapshots_total(client):
    wid = create(client, target_amount=100.0)
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "ann"})
    chip(client, wid, "bob", 100.0)
    r = client.post(f"/api/wishes/{wid}/fulfill")
    assert r.status_code == 200 and r.json()["status"] == "fulfilled"

    # post-fulfill chip-in must not alter the pinned snapshot
    chip(client, wid, "late", 50)  # 409, rejected
    done = client.get("/api/done").json()
    row = next(w for w in done if w["id"] == wid)
    assert row["pledged_snapshot"] == 100.0
    assert row["progress"]["pledged"] == 100.0
    assert row["progress"]["target"] == 100.0


def test_no_target_fulfill_has_no_funding_bar(client):
    wid = create(client)
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "ann"})
    assert client.post(f"/api/wishes/{wid}/fulfill").status_code == 200


# ---------- split tracks ----------

def test_same_person_can_claim_and_chip_in(client):
    wid = create(client, target_amount=100.0)
    assert client.post(f"/api/wishes/{wid}/claim", json={"claimer": "sam"}).status_code == 200
    assert chip(client, wid, "sam", 40).status_code == 200
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["claimer"] == "sam"
    assert [c["backer"] for c in g["chipins"]] == ["sam"]


def test_chipins_survive_release_and_reclaim(client):
    wid = create(client, target_amount=100.0)
    chip(client, wid, "bob", 60.0)
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "ann"})
    client.post(f"/api/wishes/{wid}/release")
    g = client.get(f"/api/wishes/{wid}").json()
    assert g["progress"]["pledged"] == 60.0  # sponsor track untouched by release
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "mia"})
    chip(client, wid, "zoe", 40.0)
    assert client.post(f"/api/wishes/{wid}/fulfill").status_code == 200


def test_mine_and_list_carry_progress(client):
    wid = create(client, target_amount=100.0)
    chip(client, wid, "bob", 25.0)
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "ann"})
    mine = client.get("/api/mine?claimer=ann").json()
    assert mine[0]["progress"]["pledged"] == 25.0 and mine[0]["progress"]["target"] == 100.0
    wall = client.get("/api/wishes").json()
    card = next(w for w in wall if w["id"] == wid)
    assert card["progress"]["pledged"] == 25.0 and card["chipin_count"] == 1
