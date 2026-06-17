"""Profile resync reports derived from operator notes."""

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
from hex_cortex.memory.review_propagation import (
    REVIEW_PROPAGATION_FILENAME,
    ReviewPropagationJsonlStore,
)

PROFILE_RESYNC_REPORT_FILENAME = "profile-resync-report.jsonl"


class ProfileResyncReportRecord(BaseModel):
    """One persisted profile resync report."""

    resync_id: str = Field(default_factory=lambda: f"profile_resync_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_pack_id: str | None
    source_flow_id: str | None
    pack_decision: str | None
    flow_decision: str | None
    resync_status: str
    resync_decision: str
    resync_allowed: bool
    blocker_count: int = Field(ge=0)
    active_blockers: list[str]
    next_action: str
    resync_hash: str
    reasons: list[str]


class ProfileResyncReportSummary(BaseModel):
    """Summary of persisted profile resync reports."""

    inspect_type: str = "profile_resync_report"
    path: str
    exists: bool
    total_resync_count: int = Field(ge=0)
    latest_resync_id: str | None
    latest_selected_skill: str | None
    latest_resync_status: str | None
    latest_resync_decision: str | None
    latest_resync_allowed: bool | None
    latest_blocker_count: int | None
    latest_next_action: str | None
    latest_resync_hash: str | None


class ProfileResyncReportJsonlStore:
    """Persist profile resync reports as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ProfileResyncReportRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ProfileResyncReportRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid profile resync report at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ProfileResyncReportRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ProfileResyncReportRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_profile_resync_report(profile: Path) -> dict[str, object]:
    """Build one profile resync report."""

    packs = ReviewExportPackJsonlStore(profile / REVIEW_EXPORT_PACK_FILENAME).load()
    flows = ReviewPropagationJsonlStore(profile / REVIEW_PROPAGATION_FILENAME).load()
    record = _resync_from_sources(
        profile,
        packs[-1] if packs else None,
        flows[-1] if flows else None,
    )
    path = profile / PROFILE_RESYNC_REPORT_FILENAME
    count = ProfileResyncReportJsonlStore(path).append(record)
    return {
        "resync_type": "profile_resync_report",
        "profile_path": str(profile),
        "resync_path": str(path),
        "resync_count": count,
        "resync_record": record.model_dump(mode="json"),
    }


def summarize_profile_resync_reports(path: Path) -> dict[str, object]:
    records = ProfileResyncReportJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ProfileResyncReportSummary(
        path=str(path),
        exists=path.exists(),
        total_resync_count=len(records),
        latest_resync_id=latest.resync_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_resync_status=latest.resync_status if latest else None,
        latest_resync_decision=latest.resync_decision if latest else None,
        latest_resync_allowed=latest.resync_allowed if latest else None,
        latest_blocker_count=latest.blocker_count if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_resync_hash=latest.resync_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _resync_from_sources(profile: Path, pack, flow) -> ProfileResyncReportRecord:
    selected_skill = flow.selected_skill if flow else (pack.selected_skill if pack else "profile_resync_sources_missing")
    status, decision, allowed, blockers, next_action, reasons = _resync_decision(pack, flow)
    return ProfileResyncReportRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_pack_id=pack.export_id if pack else None,
        source_flow_id=flow.propagation_id if flow else None,
        pack_decision=pack.pack_decision if pack else None,
        flow_decision=flow.propagation_decision if flow else None,
        resync_status=status,
        resync_decision=decision,
        resync_allowed=allowed,
        blocker_count=len(blockers),
        active_blockers=blockers,
        next_action=next_action,
        resync_hash=_resync_hash(selected_skill, decision, next_action, *blockers),
        reasons=reasons,
    )


def _resync_decision(pack, flow):
    if not pack:
        return "blocked", "resync_blocked", False, ["pack_missing"], "build_pack", ["pack_missing"]
    if not flow:
        return "watch", "resync_watch", False, [pack.next_action], "build_flow", ["flow_missing"]
    if flow.propagation_allowed and flow.selected_skill == pack.selected_skill:
        return "ready", "resync_ready", True, [], "prepare_freeze_stamp", ["flow_ready"]
    return "watch", "resync_watch", False, [pack.next_action], pack.next_action, ["flow_watch"]


def _resync_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
