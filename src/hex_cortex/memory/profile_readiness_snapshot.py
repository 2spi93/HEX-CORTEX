"""Append-only readiness snapshots for local profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.profile_operational_readiness import (
    inspect_profile_operational_readiness,
)

SNAPSHOT_FILENAME = "profile-readiness.jsonl"


class ProfileReadinessSnapshotRecord(BaseModel):
    """One persisted operational readiness snapshot."""

    snapshot_id: str = Field(default_factory=lambda: f"readiness_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    verdict: str
    score: float = Field(ge=0.0, le=1.0)
    blocked_reasons: list[str]
    watch_reasons: list[str]
    readiness_report: dict[str, object]


class ProfileReadinessSnapshotSummary(BaseModel):
    """Summary of persisted readiness snapshots."""

    inspect_type: str = "profile_readiness_snapshot"
    path: str
    exists: bool
    total_snapshot_count: int = Field(ge=0)
    latest_snapshot_id: str | None
    latest_verdict: str | None
    latest_score: float | None
    previous_verdict: str | None
    previous_score: float | None
    score_delta: float | None
    readiness_trend: str | None


class ProfileReadinessSnapshotJsonlStore:
    """Persist readiness snapshots as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ProfileReadinessSnapshotRecord]:
        """Load readiness snapshots."""

        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ProfileReadinessSnapshotRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid profile readiness snapshot at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ProfileReadinessSnapshotRecord]) -> int:
        """Replace JSONL content with readiness snapshots."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ProfileReadinessSnapshotRecord) -> int:
        """Append a readiness snapshot and return the new count."""

        records = self.load()
        records.append(record)
        return self.save(records)


def record_profile_readiness_snapshot(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
) -> dict[str, object]:
    """Inspect readiness and persist the result as an append-only snapshot."""

    snapshot_path = profile / SNAPSHOT_FILENAME
    readiness_report = inspect_profile_operational_readiness(
        profile,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
    )
    record = ProfileReadinessSnapshotRecord(
        profile_path=str(profile),
        verdict=str(readiness_report["verdict"]),
        score=float(readiness_report["score"]),
        blocked_reasons=list(readiness_report["blocked_reasons"]),
        watch_reasons=list(readiness_report["watch_reasons"]),
        readiness_report=readiness_report,
    )
    store = ProfileReadinessSnapshotJsonlStore(snapshot_path)
    snapshot_count = store.append(record)
    return {
        "record_type": "profile_readiness_snapshot",
        "profile_path": str(profile),
        "snapshot_path": str(snapshot_path),
        "snapshot_count": snapshot_count,
        "snapshot_record": record.model_dump(mode="json"),
    }


def summarize_profile_readiness_snapshots(path: Path) -> dict[str, object]:
    """Summarize readiness snapshots."""

    records = ProfileReadinessSnapshotJsonlStore(path).load()
    latest = records[-1] if records else None
    previous = records[-2] if len(records) > 1 else None
    score_delta = None
    readiness_trend = None
    if latest and previous:
        score_delta = round(latest.score - previous.score, 4)
        readiness_trend = _trend(score_delta, latest.verdict, previous.verdict)
    summary = ProfileReadinessSnapshotSummary(
        path=str(path),
        exists=path.exists(),
        total_snapshot_count=len(records),
        latest_snapshot_id=latest.snapshot_id if latest else None,
        latest_verdict=latest.verdict if latest else None,
        latest_score=latest.score if latest else None,
        previous_verdict=previous.verdict if previous else None,
        previous_score=previous.score if previous else None,
        score_delta=score_delta,
        readiness_trend=readiness_trend,
    )
    return summary.model_dump(mode="json")


def _trend(score_delta: float, latest_verdict: str, previous_verdict: str) -> str:
    if latest_verdict != previous_verdict:
        return "changed"
    if score_delta > 0:
        return "up"
    if score_delta < 0:
        return "down"
    return "flat"
