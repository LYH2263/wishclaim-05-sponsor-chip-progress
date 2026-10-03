"""Progress projection: derive funding progress from the chip-in ledger.

Pure functions over (pledged_total, target) so a preview can be computed
without touching the database. Target rules:

* open / released wishes track the editable ``target_amount``;
* claiming pins ``target_snapshot`` — later edits never back-fill a claim;
* a wish without a target is treated as having no funding goal.
"""
from __future__ import annotations


def effective_target(status: str, target_amount, target_snapshot):
    """Goal a wish's progress is measured against right now."""
    if status in ("claimed", "fulfilled"):
        return target_snapshot
    return target_amount


def project(pledged: float, target) -> dict:
    has_target = target is not None and target > 0
    if not has_target:
        return {
            "target": None,
            "pledged": round(float(pledged), 2),
            "remaining": None,
            "percent": None,
            "has_target": False,
            "reached": True,
        }
    remaining = max(0.0, float(target) - float(pledged))
    percent = min(100.0, round(float(pledged) / float(target) * 100, 1))
    return {
        "target": round(float(target), 2),
        "pledged": round(float(pledged), 2),
        "remaining": round(remaining, 2),
        "percent": percent,
        "has_target": True,
        "reached": float(pledged) + 1e-9 >= float(target),
    }


def preview(pledged: float, target, amount: float) -> dict:
    """Dry-run projection after a candidate chip-in. Never persisted."""
    before = project(pledged, target)
    after = project(float(pledged) + float(amount), target)
    return {
        "dry_run": True,
        "amount": round(float(amount), 2),
        "pledged_now": before["pledged"],
        "pledged_after": after["pledged"],
        "target": before["target"],
        "has_target": before["has_target"],
        "remaining_now": before["remaining"],
        "remaining_after": after["remaining"],
        "percent_now": before["percent"],
        "percent_after": after["percent"],
        "reached_now": before["reached"],
        "reached_after": after["reached"],
    }
