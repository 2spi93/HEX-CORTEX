"""Gate based on the latest profile readiness snapshot."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.memory.profile_readiness_snapshot import SNAPSHOT_FILENAME
from hex_cortex.memory.profile_readiness_snapshot import ProfileReadinessSnapshotJsonlStore
from hex_cortex.memory.profile_readiness_snapshot import ProfileReadinessSnapshotRecord


class ProfileReadinessGateDecision(StrEnum):
    """Operational gate decisions."""

    ALLOW = "allow"
    WATCH = "watch"
    BLOCK = "block"


class ProfileReadinessGateReport(BaseModel):
    """Gate report derived from the latest readiness snapshot."""

    gate_type: str = "profile_readiness_gate"
    profile_path: str
    snapshot_path: str
    snapshot_exists: bool
    decision: ProfileReadinessGateDecision
    reason: str
    minimum_ready_score: float = Field(ge=0.0, le=1.0)
    latest_snapshot_id: str | None
    latest_verdict: str | None
    latest_score: float | None
    blocked_reasons: list[str]
    watch_reasons: list[str]


def inspect_profile_readiness_gate(
    profile: Path,
    *,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Read latest readiness snapshot and return gate decision."""

    if not 0 <= minimum_ready_score <= 1:
        raise ValueError("minimum_ready_score must be between 0 and 1")
    snapshot_path = profile / SNAPSHOT_FILENAME
    records = ProfileReadinessSnapshotJsonlStore(snapshot_path).load()
    latest = records[-1] if records else None
    decision, reason = _decision_from_snapshot(
        latest,
        minimum_ready_score=minimum_ready_score,
    )
    report = ProfileReadinessGateReport(
        profile_path=str(profile),
        snapshot_path=str(snapshot_path),
        snapshot_exists=latest is not None,
        decision=decision,
        reason=reason,
        minimum_ready_score=minimum_ready_score,
        latest_snapshot_id=latest.snapshot_id if latest else None,
        latest_verdict=latest.verdict if latest else None,
        latest_score=latest.score if latest else None,
        blocked_reasons=latest.blocked_reasons if latest else [],
        watch_reasons=latest.watch_reasons if latest else [],
    )
    return report.model_dump(mode="json")


def _decision_from_snapshot(
    snapshot: ProfileReadinessSnapshotRecord | None,
    *,
    minimum_ready_score: float,
) -> tuple[ProfileReadinessGateDecision, str]:
    if snapshot is None:
        return ProfileReadinessGateDecision.BLOCK, "readiness_snapshot_missing"
    if snapshot.verdict == "profile_blocked":
        return ProfileReadinessGateDecision.BLOCK, "latest_snapshot_blocked"
    if snapshot.verdict == "profile_watch":
        return ProfileReadinessGateDecision.WATCH, "latest_snapshot_watch"
    if snapshot.score < minimum_ready_score:
        return ProfileReadinessGateDecision.WATCH, "latest_snapshot_score_below_threshold"
    return ProfileReadinessGateDecision.ALLOW, "latest_snapshot_ready"
