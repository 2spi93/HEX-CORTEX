"""Profile resync gates derived from resync reports."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.profile_resync_report import (
    PROFILE_RESYNC_REPORT_FILENAME,
    ProfileResyncReportJsonlStore,
)

PROFILE_RESYNC_GATE_FILENAME = "profile-resync-gate.jsonl"


class ProfileResyncGateRecord(BaseModel):
    """One persisted profile resync gate record."""

    gate_id: str = Field(default_factory=lambda: f"profile_resync_gate_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_resync_id: str | None
    resync_decision: str | None
    gate_status: str
    gate_decision: str
    gate_allowed: bool
    next_action: str
    gate_hash: str
    reasons: list[str]


class ProfileResyncGateSummary(BaseModel):
    """Summary of persisted profile resync gates."""

    inspect_type: str = "profile_resync_gate"
    path: str
    exists: bool
    total_gate_count: int = Field(ge=0)
    latest_gate_id: str | None
    latest_selected_skill: str | None
    latest_gate_status: str | None
    latest_gate_decision: str | None
    latest_gate_allowed: bool | None
    latest_next_action: str | None
    latest_gate_hash: str | None


class ProfileResyncGateJsonlStore:
    """Persist profile resync gates as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ProfileResyncGateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ProfileResyncGateRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid profile resync gate at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ProfileResyncGateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ProfileResyncGateRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_profile_resync_gate(profile: Path) -> dict[str, object]:
    """Build one profile resync gate."""

    resyncs = ProfileResyncReportJsonlStore(
        profile / PROFILE_RESYNC_REPORT_FILENAME
    ).load()
    if not resyncs:
        record = _missing_resync_gate(profile)
    else:
        record = _gate_from_resync(profile, resyncs[-1])
    path = profile / PROFILE_RESYNC_GATE_FILENAME
    count = ProfileResyncGateJsonlStore(path).append(record)
    return {
        "gate_type": "profile_resync_gate",
        "profile_path": str(profile),
        "gate_path": str(path),
        "gate_count": count,
        "gate_record": record.model_dump(mode="json"),
    }


def summarize_profile_resync_gates(path: Path) -> dict[str, object]:
    records = ProfileResyncGateJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ProfileResyncGateSummary(
        path=str(path),
        exists=path.exists(),
        total_gate_count=len(records),
        latest_gate_id=latest.gate_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_gate_status=latest.gate_status if latest else None,
        latest_gate_decision=latest.gate_decision if latest else None,
        latest_gate_allowed=latest.gate_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_gate_hash=latest.gate_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_resync_gate(profile: Path) -> ProfileResyncGateRecord:
    return ProfileResyncGateRecord(
        profile_path=str(profile),
        selected_skill="resync_missing",
        source_resync_id=None,
        resync_decision=None,
        gate_status="blocked",
        gate_decision="gate_blocked",
        gate_allowed=False,
        next_action="build_profile_resync_report",
        gate_hash=_gate_hash("resync_missing", "gate_blocked"),
        reasons=["resync_missing"],
    )


def _gate_from_resync(profile: Path, resync) -> ProfileResyncGateRecord:
    allowed = resync.resync_allowed and resync.resync_decision == "resync_ready"
    decision = "gate_ready" if allowed else "gate_watch"
    return ProfileResyncGateRecord(
        profile_path=str(profile),
        selected_skill=resync.selected_skill,
        source_resync_id=resync.resync_id,
        resync_decision=resync.resync_decision,
        gate_status="ready" if allowed else "watch",
        gate_decision=decision,
        gate_allowed=allowed,
        next_action="prepare_freeze_stamp" if allowed else resync.next_action,
        gate_hash=_gate_hash(resync.resync_hash, decision, resync.next_action),
        reasons=["ready" if allowed else "watch"],
    )


def _gate_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
