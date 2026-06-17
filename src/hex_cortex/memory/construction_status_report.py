"""Construction status reports for the HEX-CORTEX profile."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.review_export_pack import (
    REVIEW_EXPORT_PACK_FILENAME,
    ReviewExportPackJsonlStore,
)

CONSTRUCTION_STATUS_REPORT_FILENAME = "construction-status-report.jsonl"


class ConstructionStatusReportRecord(BaseModel):
    """One persisted construction status report."""

    status_id: str = Field(default_factory=lambda: f"construction_status_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_pack_id: str | None
    source_pack_hash: str | None
    pack_decision: str | None
    construction_status: str
    construction_decision: str
    construction_complete: bool
    blocker_count: int = Field(ge=0)
    active_blockers: list[str]
    next_action: str
    report_hash: str
    reasons: list[str]


class ConstructionStatusReportSummary(BaseModel):
    """Summary of persisted construction status reports."""

    inspect_type: str = "construction_status_report"
    path: str
    exists: bool
    total_status_count: int = Field(ge=0)
    latest_status_id: str | None
    latest_selected_skill: str | None
    latest_construction_status: str | None
    latest_construction_decision: str | None
    latest_construction_complete: bool | None
    latest_blocker_count: int | None
    latest_next_action: str | None
    latest_report_hash: str | None


class ConstructionStatusReportJsonlStore:
    """Persist construction status reports as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ConstructionStatusReportRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ConstructionStatusReportRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid construction status report at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ConstructionStatusReportRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ConstructionStatusReportRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_construction_status_report(profile: Path) -> dict[str, object]:
    """Build one construction status report."""

    packs = ReviewExportPackJsonlStore(profile / REVIEW_EXPORT_PACK_FILENAME).load()
    if not packs:
        record = _missing_pack_status(profile)
    else:
        record = _status_from_pack(profile, packs[-1])
    path = profile / CONSTRUCTION_STATUS_REPORT_FILENAME
    count = ConstructionStatusReportJsonlStore(path).append(record)
    return {
        "status_type": "construction_status_report",
        "profile_path": str(profile),
        "status_path": str(path),
        "status_count": count,
        "status_record": record.model_dump(mode="json"),
    }


def summarize_construction_status_reports(path: Path) -> dict[str, object]:
    records = ConstructionStatusReportJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ConstructionStatusReportSummary(
        path=str(path),
        exists=path.exists(),
        total_status_count=len(records),
        latest_status_id=latest.status_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_construction_status=latest.construction_status if latest else None,
        latest_construction_decision=latest.construction_decision if latest else None,
        latest_construction_complete=latest.construction_complete if latest else None,
        latest_blocker_count=latest.blocker_count if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_report_hash=latest.report_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_pack_status(profile: Path) -> ConstructionStatusReportRecord:
    return ConstructionStatusReportRecord(
        profile_path=str(profile),
        selected_skill="review_pack_missing",
        source_pack_id=None,
        source_pack_hash=None,
        pack_decision=None,
        construction_status="blocked",
        construction_decision="construction_blocked",
        construction_complete=False,
        blocker_count=1,
        active_blockers=["review_pack_missing"],
        next_action="build_review_export_pack",
        report_hash=_report_hash("review_pack_missing", "construction_blocked"),
        reasons=["review_export_pack_missing"],
    )


def _status_from_pack(profile: Path, pack) -> ConstructionStatusReportRecord:
    status, decision, complete, blockers, next_action, reasons = _status_decision(pack)
    return ConstructionStatusReportRecord(
        profile_path=str(profile),
        selected_skill=pack.selected_skill,
        source_pack_id=pack.export_id,
        source_pack_hash=pack.pack_hash,
        pack_decision=pack.pack_decision,
        construction_status=status,
        construction_decision=decision,
        construction_complete=complete,
        blocker_count=len(blockers),
        active_blockers=blockers,
        next_action=next_action,
        report_hash=_report_hash(pack.pack_hash, decision, *blockers),
        reasons=reasons,
    )


def _status_decision(pack):
    if pack.pack_decision == "pack_ready" and pack.pack_complete:
        return (
            "ready",
            "construction_ready",
            True,
            [],
            "prepare_freeze_stamp",
            ["construction_pack_ready"],
        )
    if pack.pack_decision == "pack_watch" and pack.pack_complete:
        return (
            "watch",
            "construction_watch",
            False,
            [pack.next_action],
            pack.next_action,
            ["construction_waiting_for_operator", *pack.reasons],
        )
    return (
        "blocked",
        "construction_blocked",
        False,
        [pack.next_action],
        pack.next_action,
        ["construction_pack_blocked", *pack.reasons],
    )


def _report_hash(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
