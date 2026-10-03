"""Chip-in ledger: append-only sponsor contributions.

This is the sponsor track, fully separate from the claim lock (claimer track).
The ledger table is the source of truth; wishes.pledged_total is a maintained
projection of it.
"""
import math
from datetime import datetime, timezone


def validate_amount(amount) -> dict:
    """A chip-in must be a finite number strictly greater than zero."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return {"ok": False, "reason": "invalid_amount"}
    if not math.isfinite(amount) or amount <= 0:
        return {"ok": False, "reason": "invalid_amount"}
    return {"ok": True, "reason": ""}


def normalize_backer(backer: str) -> str:
    backer = (backer or "").strip()
    return backer


def record(c, wish_id: int, backer: str, amount: float, created_at: str | None = None) -> int:
    """Append one ledger row. Caller commits."""
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    cur = c.execute(
        "INSERT INTO chipins(wish_id, backer, amount, created_at) VALUES (?,?,?,?)",
        (wish_id, backer, float(amount), created_at),
    )
    return cur.lastrowid


def total(c, wish_id: int) -> float:
    row = c.execute(
        "SELECT COALESCE(SUM(amount),0) AS t FROM chipins WHERE wish_id=?", (wish_id,)
    ).fetchone()
    return float(row["t"])


def count(c, wish_id: int) -> int:
    row = c.execute(
        "SELECT COUNT(*) AS n FROM chipins WHERE wish_id=?", (wish_id,)
    ).fetchone()
    return int(row["n"])


def entries(c, wish_id: int) -> list:
    return [
        dict(r)
        for r in c.execute(
            "SELECT id, backer, amount, created_at FROM chipins WHERE wish_id=? ORDER BY id",
            (wish_id,),
        )
    ]
