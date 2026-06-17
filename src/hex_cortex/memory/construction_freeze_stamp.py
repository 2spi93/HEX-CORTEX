"""Construction freeze stamps for HEX-CORTEX profiles."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.construction_status_report import (
    CONSTRUCTION_STATUS_REPORT_FILENAME,
    ConstructionStatusReportJsonlStore,
)

CONSTRUCTION_FREEZE_STAMP_FILENAME = "construction-freeze-stamp.jsonl"


class ConstructionFreezeStampRecord(BaseModel):
    """One persisted construction freeze stamp."""

    freeze_id: str = Field(default_factory=lambda: f"construction_freeze_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_status_id: str | None
    source_report_hash: str | None
    construction_decision: str | None
    construction_complete: bool
    freeze_status: str
    freeze_decision: str
    freeze_allowed: bool
    freeze_hash: str
    next_action: str
    reasons: list[str]


class ConstructionFreezeStampSummary(BaseModel):
    """Summary of persisted construction freeze stamps."""

    inspect_type: str = "construction_freeze_stamp"
    path: str
    exists: bool
    total_freeze_count: int = Field(ge=0)
    latest_freeze_id: str | None
    latest_selected_skill: str | None
    latest_freeze_status: str | None
    latest_freeze_decision: str | None
    latest_freeze_allowed: bool | None
    latest_next_action: str | None
    latest_freeze_hash: str | None


class ConstructionFreezeStampJsonlStore:
    """Persist construction freeze stamps as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ConstructionFreezeStampRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ConstructionFreezeStampRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid construction freeze stamp at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ConstructionFreezeStampRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ConstructionFreezeStampRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_construction_freeze_stamp(profile: Path) -> dict[str, object]:
    """Build one construction freeze stamp."""

    statuses = ConstructionStatusReportJsonlStore(
        profile / CONSTRUCTION_STATUS_REPORT_FILENAME
    ).load()
    if not statuses:
        record = _missing_status_freeze(profile)
    else:
        record = _freeze_from_status(profile, statuses[-1])
    path = profile / CONSTRUCTION_FREEZE_STAMP_FILENAME
    count = ConstructionFreezeStampJsonlStore(path).append(record)
    return {
        "freeze_type": "construction_freeze_stamp",
        "profile_path": str(profile),
        "freeze_path": str(path),
        "freeze_count": count,
        "freeze_record": record.model_dump(mode="json"),
    }


def summarize_construction_freeze_stamps(path: Path) -> dict[str, object]:
    records = ConstructionFreezeStampJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ConstructionFreezeStampSummary(
        path=str(path),
        exists=path.exists(),
        total_freeze_count=len(records),
        latest_freeze_id=latest.freeze_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_freeze_status=latest.freeze_status if latest else None,
        latest_freeze_decision=latest.freeze_decision if latest else None,
        latest_freeze_allowed=latest.freeze_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_freeze_hash=latest.freeze_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_status_freeze(profile: Path) -> ConstructionFreezeStampRecord:
    return ConstructionFreezeStampRecord(
        profile_path=str(profile),
        selected_skill="construction_status_missing",
        source_status_id=None,
        source_report_hash=None,
        construction_decision=None,
        construction_complete=False,
        freeze_status="blocked",
        freeze_decision="freeze_blocked",
        freeze_allowed=False,
        freeze_hash=_freeze_hash("construction_status_missing", "freeze_blocked"),
        next_action="build_construction_status_report",
        reasons=["construction_status_report_missing"],
    )


def _freeze_from_status(profile: Path, status) -> ConstructionFreezeStampRecord:
    freeze_status, decision, allowed, next_action, reasons = _freeze_decision(status)
    return ConstructionFreezeStampRecord(
        profile_path=str(profile),
        selected_skill=status.selected_skill,
        source_status_id=status.status_id,
        source_report_hash=status.report_hash,
        construction_decision=status.construction_decision,
        construction_complete=status.construction_complete,
        freeze_status=freeze_status,
        freeze_decision=decision,
        freeze_allowed=allowed,
        freeze_hash=_freeze_hash(status.report_hash, decision, status.next_action),
        next_action=next_action,
        reasons=reasons,
    )


def _freeze_decision(status):
    if status.construction_decision == "construction_ready" and status.construction_complete:
        return (
            "ready",
            "freeze_ready",
            True,
            "build_operator_handoff_runbook",
            ["construction_ready_for_freeze"],
        )
    if status.construction_decision == "construction_watch":
        return (
            "watch",
            "freeze_watch",
            False,
            status.next_action,
            ["construction_watch", *status.reasons],
        )
    return (
        "blocked",
        "freeze_blocked",
        False,
        status.next_action,
        ["construction_blocked", *status.reasons],
    )


def _freeze_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
