"""Compact operator status derived from the readiness gate."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from hex_cortex.memory.profile_readiness_gate import inspect_profile_readiness_gate


class ProfileOperatorStatus(BaseModel):
    """Minimal status payload for human operators."""

    status: str
    decision: str
    reason: str
    score: float | None
    latest_snapshot_id: str | None


def inspect_profile_operator_status(
    profile: Path,
    *,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Return a compact operator status from the latest readiness gate."""

    gate = inspect_profile_readiness_gate(
        profile,
        minimum_ready_score=minimum_ready_score,
    )
    status = _status_from_decision(str(gate["decision"]))
    payload = ProfileOperatorStatus(
        status=status,
        decision=str(gate["decision"]),
        reason=str(gate["reason"]),
        score=gate["latest_score"],
        latest_snapshot_id=gate["latest_snapshot_id"],
    )
    return payload.model_dump(mode="json")


def _status_from_decision(decision: str) -> str:
    if decision == "allow":
        return "ready"
    if decision == "watch":
        return "watch"
    return "blocked"
