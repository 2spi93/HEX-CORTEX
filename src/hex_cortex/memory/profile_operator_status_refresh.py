"""Refresh readiness and return compact operator status."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from hex_cortex.memory.profile_readiness_refresh import refresh_profile_readiness_gate


class ProfileOperatorStatusRefresh(BaseModel):
    """Minimal refreshed status payload for human operators."""

    status: str
    decision: str
    reason: str
    score: float | None
    latest_snapshot_id: str | None


def refresh_profile_operator_status(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Refresh readiness snapshot, evaluate gate, and return minimal status."""

    refresh = refresh_profile_readiness_gate(
        profile,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
        minimum_ready_score=minimum_ready_score,
    )
    status = _status_from_decision(str(refresh["decision"]))
    payload = ProfileOperatorStatusRefresh(
        status=status,
        decision=str(refresh["decision"]),
        reason=str(refresh["reason"]),
        score=refresh["latest_score"],
        latest_snapshot_id=refresh["latest_snapshot_id"],
    )
    return payload.model_dump(mode="json")


def _status_from_decision(decision: str) -> str:
    if decision == "allow":
        return "ready"
    if decision == "watch":
        return "watch"
    return "blocked"
