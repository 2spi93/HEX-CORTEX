"""Decide the next cognitive action from operator control status."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from hex_cortex.memory.profile_operator_control import run_profile_operator_control


class ProfileNextActionReport(BaseModel):
    """Compact next-action report for the local cortex."""

    action_type: str = "profile_next_action"
    profile_path: str
    status: str
    decision: str
    reason: str
    score: float | None
    latest_snapshot_id: str | None
    next_action: str
    next_reason: str


def inspect_profile_next_action(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Run operator control and derive the next cognitive action."""

    control = run_profile_operator_control(
        profile,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
        minimum_ready_score=minimum_ready_score,
    )
    next_action, next_reason = _next_action_from_decision(
        str(control["decision"]),
        str(control["reason"]),
    )
    report = ProfileNextActionReport(
        profile_path=str(profile),
        status=str(control["status"]),
        decision=str(control["decision"]),
        reason=str(control["reason"]),
        score=control["score"],
        latest_snapshot_id=control["latest_snapshot_id"],
        next_action=next_action,
        next_reason=next_reason,
    )
    return report.model_dump(mode="json")


def _next_action_from_decision(decision: str, reason: str) -> tuple[str, str]:
    if decision == "allow":
        return "run_cortex_pipeline", "profile_ready_for_cognitive_execution"
    if decision == "watch":
        return "review_profile_watch_reasons", reason
    return "repair_profile_readiness", reason
