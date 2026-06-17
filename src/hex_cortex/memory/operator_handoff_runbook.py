"""Operator handoff runbooks derived from final seal stamps."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.final_seal_stamp import (
    FINAL_SEAL_STAMP_FILENAME,
    FinalSealStampJsonlStore,
)

OPERATOR_HANDOFF_RUNBOOK_FILENAME = "operator-handoff-runbook.jsonl"


class OperatorHandoffRunbookRecord(BaseModel):
    """One persisted operator handoff runbook record."""

    runbook_id: str = Field(default_factory=lambda: f"operator_handoff_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str | None
    source_seal_id: str | None
    source_seal_hash: str | None
    source_seal_decision: str | None
    source_end_state: str | None
    handoff_status: str
    handoff_decision: str
    handoff_allowed: bool
    runbook_hash: str
    next_action: str
    required_operator_checks: list[str]
    reasons: list[str]


class OperatorHandoffRunbookSummary(BaseModel):
    """Summary of persisted operator handoff runbooks."""

    inspect_type: str = "operator_handoff_runbook"
    path: str
    exists: bool
    total_runbook_count: int = Field(ge=0)
    latest_runbook_id: str | None
    latest_selected_skill: str | None
    latest_source_seal_id: str | None
    latest_handoff_status: str | None
    latest_handoff_decision: str | None
    latest_handoff_allowed: bool | None
    latest_next_action: str | None
    latest_runbook_hash: str | None


class OperatorHandoffRunbookJsonlStore:
    """Persist operator handoff runbooks as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[OperatorHandoffRunbookRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        OperatorHandoffRunbookRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid operator handoff runbook at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[OperatorHandoffRunbookRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: OperatorHandoffRunbookRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_operator_handoff_runbook(profile: Path) -> dict[str, object]:
    """Build one operator handoff runbook from the latest final seal stamp."""

    seals = FinalSealStampJsonlStore(profile / FINAL_SEAL_STAMP_FILENAME).load()
    record = _runbook_from_seal(profile, seals[-1] if seals else None)
    path = profile / OPERATOR_HANDOFF_RUNBOOK_FILENAME
    count = OperatorHandoffRunbookJsonlStore(path).append(record)
    return {
        "runbook_type": "operator_handoff_runbook",
        "profile_path": str(profile),
        "runbook_path": str(path),
        "runbook_count": count,
        "runbook_record": record.model_dump(mode="json"),
    }


def summarize_operator_handoff_runbooks(path: Path) -> dict[str, object]:
    records = OperatorHandoffRunbookJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = OperatorHandoffRunbookSummary(
        path=str(path),
        exists=path.exists(),
        total_runbook_count=len(records),
        latest_runbook_id=latest.runbook_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_source_seal_id=latest.source_seal_id if latest else None,
        latest_handoff_status=latest.handoff_status if latest else None,
        latest_handoff_decision=latest.handoff_decision if latest else None,
        latest_handoff_allowed=latest.handoff_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_runbook_hash=latest.runbook_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _runbook_from_seal(profile: Path, seal) -> OperatorHandoffRunbookRecord:
    blockers = _handoff_blockers(seal)
    allowed = len(blockers) == 0
    decision = "operator_handoff_ready" if allowed else "operator_handoff_blocked"
    next_action = "operator_runtime_ready" if allowed else "build_final_seal_stamp"
    checks = (
        [
            "confirm_profile_path",
            "confirm_final_seal_hash",
            "confirm_registry_unchanged",
            "confirm_no_pending_blockers",
        ]
        if allowed
        else []
    )
    reasons = ["final_seal_ready", "operator_handoff_prepared"] if allowed else blockers
    source_hash = seal.seal_hash if seal else None
    runbook_hash = _runbook_hash(
        str(profile),
        source_hash or "seal_missing",
        decision,
        next_action,
        *checks,
        *reasons,
    )
    return OperatorHandoffRunbookRecord(
        profile_path=str(profile),
        selected_skill=seal.selected_skill if seal else "seal_missing",
        source_seal_id=seal.seal_id if seal else None,
        source_seal_hash=source_hash,
        source_seal_decision=seal.seal_decision if seal else None,
        source_end_state=seal.source_end_state if seal else None,
        handoff_status="ready" if allowed else "blocked",
        handoff_decision=decision,
        handoff_allowed=allowed,
        runbook_hash=runbook_hash,
        next_action=next_action,
        required_operator_checks=checks,
        reasons=reasons,
    )


def _handoff_blockers(seal) -> list[str]:
    if seal is None:
        return ["final_seal_stamp_missing"]
    blockers: list[str] = []
    if seal.seal_allowed is not True:
        blockers.append("seal_not_allowed")
    if seal.seal_status != "ready":
        blockers.append("seal_status_not_ready")
    if seal.seal_decision != "final_seal_ready":
        blockers.append("seal_decision_not_ready")
    if seal.registry_change_applied is not False:
        blockers.append("registry_changed_after_seal")
    if seal.next_action != "build_operator_handoff_runbook":
        blockers.append("seal_next_action_not_operator_handoff")
    return blockers


def _runbook_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
