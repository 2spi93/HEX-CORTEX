"""Profile health history JSONL store."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.profile_health import ProfileHealthReport


class ProfileHealthHistoryRecord(BaseModel):
    """One recorded profile health snapshot."""

    history_id: str = Field(default_factory=lambda: f"health_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    overall_score: float = Field(ge=0.0, le=1.0)
    status: str
    spine_integrity_ok: bool
    total_events: int = Field(ge=0)
    total_memory_count: int = Field(ge=0)
    visible_memory_count: int = Field(ge=0)
    hidden_memory_count: int = Field(ge=0)
    average_memory_confidence: float = Field(ge=0.0, le=1.0)
    active_skill_count: int = Field(ge=0)
    pruning_audit_count: int = Field(ge=0)
    latest_pruning_operation: str | None = None

    @classmethod
    def from_report(cls, report: ProfileHealthReport) -> ProfileHealthHistoryRecord:
        """Create a history record from a profile health report."""

        return cls(
            profile_path=report.profile_path,
            overall_score=report.overall_score,
            status=report.status.value,
            spine_integrity_ok=report.spine_integrity_ok,
            total_events=report.total_events,
            total_memory_count=report.total_memory_count,
            visible_memory_count=report.visible_memory_count,
            hidden_memory_count=report.hidden_memory_count,
            average_memory_confidence=report.average_memory_confidence,
            active_skill_count=report.active_skill_count,
            pruning_audit_count=report.pruning_audit_count,
            latest_pruning_operation=report.latest_pruning_operation,
        )


class ProfileHealthHistorySummary(BaseModel):
    """Compact profile health trend summary."""

    total_history_count: int = Field(ge=0)
    latest_score: float | None = None
    previous_score: float | None = None
    score_delta: float | None = None
    trend: str = "none"
    latest_status: str | None = None


class ProfileHealthHistoryJsonlStore:
    """Persist profile health snapshots as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ProfileHealthHistoryRecord]:
        """Load profile health history records."""

        if not self.path.exists():
            return []

        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    records.append(ProfileHealthHistoryRecord.model_validate(payload))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid profile health record at line {line_number}") from exc
        return records

    def save(self, records: list[ProfileHealthHistoryRecord]) -> int:
        """Replace profile health history content."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ProfileHealthHistoryRecord) -> int:
        """Append one profile health history record."""

        records = self.load()
        records.append(record)
        return self.save(records)

    def summarize(self) -> ProfileHealthHistorySummary:
        """Summarize history trend."""

        return summarize_profile_health_history(self.load())


def summarize_profile_health_history(
    records: list[ProfileHealthHistoryRecord],
) -> ProfileHealthHistorySummary:
    """Build a compact score trend summary."""

    if not records:
        return ProfileHealthHistorySummary(total_history_count=0)

    latest = records[-1]
    previous = records[-2] if len(records) >= 2 else None
    previous_score = previous.overall_score if previous else None
    score_delta = (
        round(latest.overall_score - previous.overall_score, 4) if previous else None
    )
    trend = _trend_from_delta(score_delta)
    return ProfileHealthHistorySummary(
        total_history_count=len(records),
        latest_score=latest.overall_score,
        previous_score=previous_score,
        score_delta=score_delta,
        trend=trend,
        latest_status=latest.status,
    )


def _trend_from_delta(delta: float | None) -> str:
    if delta is None:
        return "none"
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"
