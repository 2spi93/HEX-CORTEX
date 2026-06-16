"""Single operator control entrypoint for profile readiness."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.memory.profile_operator_status_history import (
    record_profile_operator_status_history,
)


class ProfileOperatorControlReport(BaseModel):
    """Compact control report for human operators."""

    control_type: str = "profile_operator_control"
    profile_path: str
    status: str
    decision: str
    reason: str
    score: float | None
    latest_snapshot_id: str | None
    status_id: str
    history_count: int = Field(ge=0)
    history_path: str


def run_profile_operator_control(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Refresh readiness, record operator history, and return compact status."""

    history_payload = record_profile_operator_status_history(
        profile,
        refresh=True,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
        minimum_ready_score=minimum_ready_score,
    )
    status_record = history_payload["status_record"]
    report = ProfileOperatorControlReport(
        profile_path=str(profile),
        status=str(status_record["status"]),
        decision=str(status_record["decision"]),
        reason=str(status_record["reason"]),
        score=status_record["score"],
        latest_snapshot_id=status_record["latest_snapshot_id"],
        status_id=str(status_record["status_id"]),
        history_count=int(history_payload["history_count"]),
        history_path=str(history_payload["history_path"]),
    )
    return report.model_dump(mode="json")
