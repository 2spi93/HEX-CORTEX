"""Operator runtime readiness markers derived from handoff runbooks."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.operator_handoff_runbook import (
    OPERATOR_HANDOFF_RUNBOOK_FILENAME,
    OperatorHandoffRunbookJsonlStore,
)

OPERATOR_RUNTIME_READY_FILENAME = "operator-runtime-ready.jsonl"


class OperatorRuntimeReadyRecord(BaseModel):
    """One persisted operator runtime readiness marker."""

    ready_id: str = Field(default_factory=lambda: f"operator_runtime_ready_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str | None
    source_runbook_id: str | None
    source_runbook_hash: str | None
    runtime_status: str
    runtime_decision: str
    runtime_allowed: bool
    runtime_hash: str
    next_action: str
    reasons: list[str]


class OperatorRuntimeReadySummary(BaseModel):
    """Summary of persisted operator runtime readiness markers."""

    inspect_type: str = "operator_runtime_ready"
    path: str
    exists: bool
    total_ready_count: int = Field(ge=0)
    latest_ready_id: str | None
    latest_selected_skill: str | None
    latest_source_runbook_id: str | None
    latest_runtime_status: str | None
    latest_runtime_decision: str | None
    latest_runtime_allowed: bool | None
    latest_next_action: str | None
    latest_runtime_hash: str | None


class OperatorRuntimeReadyJsonlStore:
    """Persist operator runtime readiness markers as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[OperatorRuntimeReadyRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(OperatorRuntimeReadyRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid operator runtime ready marker at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[OperatorRuntimeReadyRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: OperatorRuntimeReadyRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_operator_runtime_ready(profile: Path) -> dict[str, object]:
    """Build one operator runtime readiness marker from the latest handoff runbook."""

    runbooks = OperatorHandoffRunbookJsonlStore(
        profile / OPERATOR_HANDOFF_RUNBOOK_FILENAME
    ).load()
    record = _ready_from_runbook(profile, runbooks[-1] if runbooks else None)
    path = profile / OPERATOR_RUNTIME_READY_FILENAME
    count = OperatorRuntimeReadyJsonlStore(path).append(record)
    return {
        "ready_type": "operator_runtime_ready",
        "profile_path": str(profile),
        "ready_path": str(path),
        "ready_count": count,
        "ready_record": record.model_dump(mode="json"),
    }


def summarize_operator_runtime_ready(path: Path) -> dict[str, object]:
    records = OperatorRuntimeReadyJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = OperatorRuntimeReadySummary(
        path=str(path),
        exists=path.exists(),
        total_ready_count=len(records),
        latest_ready_id=latest.ready_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_source_runbook_id=latest.source_runbook_id if latest else None,
        latest_runtime_status=latest.runtime_status if latest else None,
        latest_runtime_decision=latest.runtime_decision if latest else None,
        latest_runtime_allowed=latest.runtime_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_runtime_hash=latest.runtime_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _ready_from_runbook(profile: Path, runbook) -> OperatorRuntimeReadyRecord:
    blockers = _runtime_blockers(runbook)
    allowed = len(blockers) == 0
    decision = "operator_runtime_ready" if allowed else "operator_runtime_blocked"
    next_action = "await_operator_command" if allowed else "build_operator_handoff_runbook"
    reasons = ["operator_handoff_ready", "runtime_marker_prepared"] if allowed else blockers
    source_hash = runbook.runbook_hash if runbook else None
    runtime_hash = _runtime_hash(
        str(profile),
        source_hash or "runbook_missing",
        decision,
        next_action,
        *reasons,
    )
    return OperatorRuntimeReadyRecord(
        profile_path=str(profile),
        selected_skill=runbook.selected_skill if runbook else "runbook_missing",
        source_runbook_id=runbook.runbook_id if runbook else None,
        source_runbook_hash=source_hash,
        runtime_status="ready" if allowed else "blocked",
        runtime_decision=decision,
        runtime_allowed=allowed,
        runtime_hash=runtime_hash,
        next_action=next_action,
        reasons=reasons,
    )


def _runtime_blockers(runbook) -> list[str]:
    if runbook is None:
        return ["operator_handoff_runbook_missing"]
    blockers: list[str] = []
    if runbook.handoff_allowed is not True:
        blockers.append("handoff_not_allowed")
    if runbook.handoff_status != "ready":
        blockers.append("handoff_status_not_ready")
    if runbook.handoff_decision != "operator_handoff_ready":
        blockers.append("handoff_decision_not_ready")
    if runbook.next_action != "operator_runtime_ready":
        blockers.append("handoff_next_action_not_runtime_ready")
    return blockers


def _runtime_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
