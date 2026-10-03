from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.claim_lock import claim_allowed, lock_payload, release_if_expired
from app.modules import chipin_ledger as ledger
from app.modules import chipin_progress as progress
from app.modules import fulfill_gate

app = FastAPI(title="Wishclaim", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup(): seed.init_db()

def now(): return datetime.now(timezone.utc)

def ttl():
    c = connect(); row = c.execute("SELECT value FROM settings WHERE key='ttl_seconds'").fetchone(); c.close()
    return int(row["value"] if row else 86400)

def sweep(c):
    for r in c.execute("SELECT * FROM wishes WHERE status='claimed'"):
        rel = release_if_expired(r["status"], r["expires_at"], now())
        if rel:
            c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=?, target_snapshot=? WHERE id=?",
                      (rel["status"], None, None, None, None, r["id"]))

def serialize(r: dict, chipin_count: int = 0) -> dict:
    w = dict(r)
    target = progress.effective_target(w["status"], w.get("target_amount"), w.get("target_snapshot"))
    # Fulfilled wishes read the cumulative total pinned at write-off.
    pledged = w.get("pledged_snapshot") if w["status"] == "fulfilled" and w.get("pledged_snapshot") is not None else (w.get("pledged_total") or 0.0)
    w["progress"] = progress.project(pledged, target)
    w["chipin_count"] = chipin_count
    return w

def chipin_counts(c, ids: list[int]) -> dict:
    if not ids:
        return {}
    q = "SELECT wish_id, COUNT(*) n FROM chipins WHERE wish_id IN (%s) GROUP BY wish_id" % ",".join("?" * len(ids))
    return {row["wish_id"]: row["n"] for row in c.execute(q, ids)}

@app.get("/api/health")
def health(): return {"ok": True, "project": "wishclaim"}

@app.get("/api/wishes")
def list_wishes():
    c = connect(); sweep(c); c.commit()
    rows = [dict(r) for r in c.execute("SELECT * FROM wishes ORDER BY id DESC")]
    counts = chipin_counts(c, [r["id"] for r in rows])
    c.close()
    return [serialize(r, counts.get(r["id"], 0)) for r in rows]

@app.get("/api/wishes/{wid}")
def get_wish(wid: int):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    out = serialize(dict(r), ledger.count(c, wid))
    out["chipins"] = ledger.entries(c, wid)
    c.close()
    return out

class WishIn(BaseModel):
    title: str
    note: str = ""
    target_amount: float | None = None

@app.post("/api/wishes")
def create_wish(body: WishIn):
    vt = fulfill_gate.validate_target(body.target_amount)
    if not vt["ok"]:
        raise HTTPException(400, vt["reason"])
    c = connect()
    cur = c.execute("INSERT INTO wishes(title,note,status,data_quality,target_amount) VALUES (?,?,?,?,?)",
                    (body.title, body.note, "open", "clean", body.target_amount))
    c.commit(); wid = cur.lastrowid; c.close(); return {"id": wid}

class TargetIn(BaseModel):
    target_amount: float | None = None

@app.patch("/api/wishes/{wid}/target")
def update_target(wid: int, body: TargetIn):
    vt = fulfill_gate.validate_target(body.target_amount)
    if not vt["ok"]:
        raise HTTPException(400, vt["reason"])
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    gate = fulfill_gate.target_editable(r["status"])
    if not gate["ok"]:
        c.close(); raise HTTPException(409, gate["reason"])
    c.execute("UPDATE wishes SET target_amount=? WHERE id=?", (body.target_amount, wid))
    c.commit()
    row = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    out = serialize(dict(row)); c.close(); return out

class ClaimIn(BaseModel):
    claimer: str

@app.post("/api/wishes/{wid}/claim")
def claim(wid: int, body: ClaimIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    allowed = claim_allowed(r["status"], r["claimer"], now(), r["expires_at"])
    if not allowed["ok"]:
        c.close(); raise HTTPException(409, allowed["reason"])
    p = lock_payload(body.claimer, now(), ttl())
    # Pin the funding goal at claim time; later target edits never back-fill.
    c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=?, target_snapshot=? WHERE id=?",
              (p["status"], p["claimer"], p["claimed_at"], p["expires_at"], r["target_amount"], wid))
    c.commit(); c.close(); return p

@app.post("/api/wishes/{wid}/release")
def release(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "not_claimed")
    c.execute("UPDATE wishes SET status='released', claimer=NULL, claimed_at=NULL, expires_at=NULL, "
              "target_snapshot=NULL WHERE id=?", (wid,))
    c.commit(); c.close(); return {"ok": True, "status": "released"}

@app.post("/api/wishes/{wid}/fulfill")
def fulfill(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    target = progress.effective_target(r["status"], r["target_amount"], r["target_snapshot"])
    proj = progress.project(r["pledged_total"] or 0.0, target)
    gate = fulfill_gate.can_fulfill(r["status"], proj)
    if not gate["ok"]:
        # Stays claimed: lock and expiry untouched.
        c.close(); raise HTTPException(409, gate["reason"])
    # Pin the cumulative total at write-off so the done page shows the snapshot.
    c.execute("UPDATE wishes SET status='fulfilled', pledged_snapshot=? WHERE id=?",
              (r["pledged_total"] or 0.0, wid))
    c.commit()
    row = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    out = serialize(dict(row)); c.close(); return out

class ChipInIn(BaseModel):
    backer: str
    amount: float

def _parse_chipin(body: ChipInIn):
    backer = ledger.normalize_backer(body.backer)
    if not backer:
        raise HTTPException(400, "invalid_backer")
    va = ledger.validate_amount(body.amount)
    if not va["ok"]:
        raise HTTPException(400, va["reason"])
    return backer, float(body.amount)

def _wish_target(r):
    return progress.effective_target(r["status"], r["target_amount"], r["target_snapshot"])

@app.post("/api/wishes/{wid}/chipin/preview")
def chipin_preview(wid: int, body: ChipInIn):
    backer, amount = _parse_chipin(body)
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] == "fulfilled": c.close(); raise HTTPException(409, "already_fulfilled")
    p = progress.preview(r["pledged_total"] or 0.0, _wish_target(r), amount)
    p["backer"] = backer
    c.close(); return p

@app.post("/api/wishes/{wid}/chipin/confirm")
def chipin_confirm(wid: int, body: ChipInIn):
    backer, amount = _parse_chipin(body)
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] == "fulfilled": c.close(); raise HTTPException(409, "already_fulfilled")
    ledger.record(c, wid, backer, amount)
    total = ledger.total(c, wid)
    c.execute("UPDATE wishes SET pledged_total=? WHERE id=?", (total, wid))
    c.commit()
    row = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    out = serialize(dict(row), ledger.count(c, wid))
    c.close(); return out

@app.get("/api/mine")
def mine(claimer: str):
    c = connect(); sweep(c); c.commit()
    rows = [dict(r) for r in c.execute("SELECT * FROM wishes WHERE claimer=?", (claimer,))]
    counts = chipin_counts(c, [r["id"] for r in rows])
    c.close()
    return [serialize(r, counts.get(r["id"], 0)) for r in rows]

@app.get("/api/done")
def done():
    c = connect()
    rows = [dict(r) for r in c.execute("SELECT * FROM wishes WHERE status='fulfilled' ORDER BY id DESC")]
    counts = chipin_counts(c, [r["id"] for r in rows])
    c.close()
    return [serialize(r, counts.get(r["id"], 0)) for r in rows]

@app.get("/api/settings")
def settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

@app.get("/api/rules")
def rules():
    return {
        "mutex": "同一愿望同时只能被一人认领",
        "ttl": "认领超时未核销则自动释放",
        "fulfill": "核销后状态变为 fulfilled",
        "chipin": "设了目标金额的愿望需凑满份子才能核销；单笔赞助必须大于 0",
        "tracks": "认领与赞助分轨记账；同一人可以既认领又赞助",
        "target_snapshot": "目标金额在认领时快照锁定，认领后改价不回刷；仅未认领愿望可改目标",
    }
