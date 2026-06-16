"""Append-only dispatch history for profile next-action execution."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

DISPATCH_HISTORY_FILENAME = "profile-dispatch.jsonl"


class ProfileDispatchHistoryRecord(BaseModel):
    """One compact dispatch history record."""

    dispatch_id: str = Field(default_factory=lambda: f"dispatch_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    status: str
    decision: str
    reason: str
    next_action: str
    next_reason: str
    safety_status: str | None = None
    safety_reasons: list[str] = Field(default_factory=list)
    dispatch_status: str
    dispatch_reason: str
    task_id: str | None
    pipeline_mode: str | None
    clock_completed: bool | None
    persisted_event_count: int | None
    persisted_memory_count: int | None


class ProfileDispatchHistorySummary(BaseModel):
    """Summary of persisted dispatch history."""

    inspect_type: str = "profile_dispatch_history"
    path: str
    exists: bool
    total_dispatch_count: int = Field(ge=0)
    executed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    latest_dispatch_id: str | None
    latest_dispatch_status: str | None
    latest_dispatch_reason: str | None
    latest_safety_status: str | None
    latest_safety_reasons: list[str]
    latest_next_action: str | None
    latest_task_id: str | None
    latest_pipeline_mode: str | None
    latest_clock_completed: bool | None


class ProfileDispatchHistoryJsonlStore:
    """Persist dispatch history as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ProfileDispatchHistoryRecord]:
        """Load dispatch history records."""

        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ProfileDispatchHistoryRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid profile dispatch history at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ProfileDispatchHistoryRecord]) -> int:
        """Replace JSONL content with dispatch records."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ProfileDispatchHistoryRecord) -> int:
        """Append one dispatch record and return the new count."""

        records = self.load()
        records.append(record)
        return self.save(records)


def record_profile_dispatch_history(
    profile: Path,
    dispatch_report: dict[str, object],
) -> dict[str, object]:
    """Persist a compact dispatch history record from a dispatch report."""

    pipeline_result = dispatch_report.get("pipeline_result")
    if not isinstance(pipeline_result, dict):
        pipeline_result = {}
    record = ProfileDispatchHistoryRecord(
        profile_path=str(profile),
        status=str(dispatch_report["status"]),
        decision=str(dispatch_report["decision"]),
        reason=str(dispatch_report["reason"]),
        next_action=str(dispatch_report["next_action"]),
        next_reason=str(dispatch_report["next_reason"]),
        safety_status=_optional_str(dispatch_report.get("safety_status")),
        safety_reasons=_optional_str_list(dispatch_report.get("safety_reasons")),
        dispatch_status=str(dispatch_report["dispatch_status"]),
        dispatch_reason=str(dispatch_report["dispatch_reason"]),
        task_id=_optional_str(pipeline_result.get("task_id")),
        pipeline_mode=_optional_str(pipeline_result.get("mode")),
        clock_completed=_optional_bool(pipeline_result.get("clock_completed")),
        persisted_event_count=_optional_int(
            pipeline_result.get("persisted_event_count")
        ),
        persisted_memory_count=_optional_int(
            pipeline_result.get("persisted_memory_count")
        ),
    )
    history_path = profile / DISPATCH_HISTORY_FILENAME
    history_count = ProfileDispatchHistoryJsonlStore(history_path).append(record)
    return {
        "record_type": "profile_dispatch_history",
        "profile_path": str(profile),
        "history_path": str(history_path),
        "history_count": history_count,
        "dispatch_record": record.model_dump(mode="json"),
    }


def summarize_profile_dispatch_history(path: Path) -> dict[str, object]:
    """Summarize persisted dispatch history."""

    records = ProfileDispatchHistoryJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ProfileDispatchHistorySummary(
        path=str(path),
        exists=path.exists(),
        total_dispatch_count=len(records),
        executed_count=sum(
            1 for record in records if record.dispatch_status == "executed"
        ),
        skipped_count=sum(
            1 for record in records if record.dispatch_status == "skipped"
        ),
        latest_dispatch_id=latest.dispatch_id if latest else None,
        latest_dispatch_status=latest.dispatch_status if latest else None,
        latest_dispatch_reason=latest.dispatch_reason if latest else None,
        latest_safety_status=latest.safety_status if latest else None,
        latest_safety_reasons=latest.safety_reasons if latest else [],
        latest_next_action=latest.next_action if latest else None,
        latest_task_id=latest.task_id if latest else None,
        latest_pipeline_mode=latest.pipeline_mode if latest else None,
        latest_clock_completed=latest.clock_completed if latest else None,
    )
    return summary.model_dump(mode="json")


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
