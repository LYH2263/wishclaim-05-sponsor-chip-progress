"""Fulfillment gate + target snapshot policy.

A claimed wish with a funding goal may only be written off (fulfilled) once
pledged total meets its *snapshot* target. Failing the gate leaves the wish
claimed — the lock is not released as a side effect. Wishes without a target
have no funding bar and fulfill as before.

Target edits are only allowed while the wish is unclaimed; the snapshot taken
at claim time is never back-filled.
"""
from __future__ import annotations

EDITABLE_STATUSES = ("open", "released")


def target_editable(status: str) -> dict:
    if status in EDITABLE_STATUSES:
        return {"ok": True, "reason": ""}
    return {"ok": False, "reason": "target_locked_after_claim"}


def validate_target(target) -> dict:
    """Target is either unset (None) or a finite positive number."""
    if target is None:
        return {"ok": True, "reason": ""}
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        return {"ok": False, "reason": "invalid_target"}
    import math
    if not math.isfinite(target) or target <= 0:
        return {"ok": False, "reason": "invalid_target"}
    return {"ok": True, "reason": ""}


def can_fulfill(status: str, projection: dict) -> dict:
    """Decision only; the caller persists nothing on failure."""
    if status != "claimed":
        return {"ok": False, "reason": "need_claim"}
    if projection["has_target"] and not projection["reached"]:
        return {"ok": False, "reason": "goal_not_reached"}
    return {"ok": True, "reason": ""}
