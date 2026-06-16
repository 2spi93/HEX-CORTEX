"""Safety gate for profile next-action dispatch."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class ProfileDispatchSafetyReport(BaseModel):
    """Safety report for dispatch execution."""

    safety_type: str = "profile_dispatch_safety"
    profile_path: str
    safety_status: str
    allowed: bool
    safety_reasons: list[str]


def inspect_profile_dispatch_safety(
    profile: Path,
    next_payload: dict[str, object],
) -> dict[str, object]:
    """Return whether a next-action payload may be executed."""

    reasons = []
    if next_payload.get("status") != "ready":
        reasons.append("profile_status_not_ready")
    if next_payload.get("decision") != "allow":
        reasons.append("operator_decision_not_allow")
    if next_payload.get("next_action") != "run_cortex_pipeline":
        reasons.append("next_action_not_dispatchable")
    if not next_payload.get("latest_snapshot_id"):
        reasons.append("latest_snapshot_missing")
    allowed = not reasons
    report = ProfileDispatchSafetyReport(
        profile_path=str(profile),
        safety_status="allow" if allowed else "block",
        allowed=allowed,
        safety_reasons=reasons,
    )
    return report.model_dump(mode="json")
