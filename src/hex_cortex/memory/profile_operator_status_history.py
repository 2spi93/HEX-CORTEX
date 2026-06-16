"""Append-only compact operator status history."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.profile_operator_status import inspect_profile_operator_status
from hex_cortex.memory.profile_operator_status_refresh import (
    refresh_profile_operator_status,
)

STATUS_HISTORY_FILENAME = "profile-operator-status.jsonl"


class ProfileOperatorStatusHistoryRecord(BaseModel):
    """One compact operator status history record."""

    status_id: str = Field(default_factory=lambda: f"opstatus_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    status: str
    decision: str
    reason: str
    score: float | None
    latest_snapshot_id: str | None


class ProfileOperatorStatusHistorySummary(BaseModel):
    """Summary of compact operator status history."""

    inspect_type: str = "profile_operator_status_history"
    path: str
    exists: bool
    total_status_count: int = Field(ge=0)
    latest_status_id: str | None
    latest_status: str | None
    latest_decision: str | None
    latest_reason: str | None
    latest_score: float | None
    latest_snapshot_id: str | None
    previous_status: str | None
    previous_decision: str | None
    previous_score: float | None
    score_delta: float | None
    status_trend: str | None


class ProfileOperatorStatusHistoryJsonlStore:
    """Persist compact operator status records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ProfileOperatorStatusHistoryRecord]:
        """Load operator status history."""

        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ProfileOperatorStatusHistoryRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid profile operator status at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ProfileOperatorStatusHistoryRecord]) -> int:
        """Replace JSONL content with operator status records."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ProfileOperatorStatusHistoryRecord) -> int:
        """Append one operator status record and return the new count."""

        records = self.load()
        records.append(record)
        return self.save(records)


def record_profile_operator_status_history(
    profile: Path,
    *,
    refresh: bool = False,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Record compact operator status history."""

    if refresh:
        status_payload = refresh_profile_operator_status(
            profile,
            policy_limit=policy_limit,
            policy_stability_window=policy_stability_window,
            minimum_ready_score=minimum_ready_score,
        )
    else:
        status_payload = inspect_profile_operator_status(
            profile,
            minimum_ready_score=minimum_ready_score,
        )
    record = ProfileOperatorStatusHistoryRecord(
        profile_path=str(profile),
        status=str(status_payload["status"]),
        decision=str(status_payload["decision"]),
        reason=str(status_payload["reason"]),
        score=status_payload["score"],
        latest_snapshot_id=status_payload["latest_snapshot_id"],
    )
    history_path = profile / STATUS_HISTORY_FILENAME
    history_count = ProfileOperatorStatusHistoryJsonlStore(history_path).append(record)
    return {
        "record_type": "profile_operator_status_history",
        "profile_path": str(profile),
        "history_path": str(history_path),
        "history_count": history_count,
        "status_record": record.model_dump(mode="json"),
    }


def summarize_profile_operator_status_history(path: Path) -> dict[str, object]:
    """Summarize compact operator status history."""

    records = ProfileOperatorStatusHistoryJsonlStore(path).load()
    latest = records[-1] if records else None
    previous = records[-2] if len(records) > 1 else None
    score_delta = None
    status_trend = None
    if latest and previous and latest.score is not None and previous.score is not None:
        score_delta = round(latest.score - previous.score, 4)
        status_trend = _trend(score_delta, latest.status, previous.status)
    elif latest and previous:
        status_trend = "changed" if latest.status != previous.status else "flat"
    summary = ProfileOperatorStatusHistorySummary(
        path=str(path),
        exists=path.exists(),
        total_status_count=len(records),
        latest_status_id=latest.status_id if latest else None,
        latest_status=latest.status if latest else None,
        latest_decision=latest.decision if latest else None,
        latest_reason=latest.reason if latest else None,
        latest_score=latest.score if latest else None,
        latest_snapshot_id=latest.latest_snapshot_id if latest else None,
        previous_status=previous.status if previous else None,
        previous_decision=previous.decision if previous else None,
        previous_score=previous.score if previous else None,
        score_delta=score_delta,
        status_trend=status_trend,
    )
    return summary.model_dump(mode="json")


def _trend(score_delta: float, latest_status: str, previous_status: str) -> str:
    if latest_status != previous_status:
        return "changed"
    if score_delta > 0:
        return "up"
    if score_delta < 0:
        return "down"
    return "flat"
