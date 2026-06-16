"""Refresh readiness snapshot and return the derived gate decision."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.memory.profile_readiness_gate import inspect_profile_readiness_gate
from hex_cortex.memory.profile_readiness_snapshot import (
    SNAPSHOT_FILENAME,
    record_profile_readiness_snapshot,
    summarize_profile_readiness_snapshots,
)


class ProfileReadinessGateSnapshotRefreshReport(BaseModel):
    """Report for the snapshot refresh plus gate decision."""

    refresh_type: str = "profile_readiness_gate_snapshot_refresh"
    profile_path: str
    snapshot_path: str
    snapshot_count: int = Field(ge=0)
    latest_snapshot_id: str | None
    latest_verdict: str | None
    latest_score: float | None
    decision: str
    reason: str
    gate_report: dict[str, object]
    snapshot_summary: dict[str, object]
    snapshot_record: dict[str, object]


def refresh_profile_readiness_gate(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Record a fresh readiness snapshot, then evaluate the snapshot gate."""

    snapshot_payload = record_profile_readiness_snapshot(
        profile,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
    )
    gate_report = inspect_profile_readiness_gate(
        profile,
        minimum_ready_score=minimum_ready_score,
    )
    snapshot_summary = summarize_profile_readiness_snapshots(
        profile / SNAPSHOT_FILENAME,
    )
    report = ProfileReadinessGateSnapshotRefreshReport(
        profile_path=str(profile),
        snapshot_path=str(profile / SNAPSHOT_FILENAME),
        snapshot_count=int(snapshot_payload["snapshot_count"]),
        latest_snapshot_id=snapshot_summary["latest_snapshot_id"],
        latest_verdict=snapshot_summary["latest_verdict"],
        latest_score=snapshot_summary["latest_score"],
        decision=str(gate_report["decision"]),
        reason=str(gate_report["reason"]),
        gate_report=gate_report,
        snapshot_summary=snapshot_summary,
        snapshot_record=snapshot_payload["snapshot_record"],
    )
    return report.model_dump(mode="json")
