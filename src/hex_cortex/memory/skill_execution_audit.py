"""Audit trail for controlled skill execution staging."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.controlled_skill_gate import (
    CONTROLLED_SKILL_GATE_FILENAME,
    ControlledSkillGateJsonlStore,
)

SKILL_EXECUTION_AUDIT_FILENAME = "skill-execution-audit.jsonl"


class SkillExecutionAuditRecord(BaseModel):
    """One persisted audit record for staged skill execution."""

    audit_id: str = Field(default_factory=lambda: f"skill_audit_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_gate_id: str | None
    selected_skill: str
    selected_action: str
    audit_status: str
    audit_decision: str
    execution_allowed: bool
    execution_mode: str
    audit_stage: str
    next_action: str
    gate_decision: str | None
    gate_confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


class SkillExecutionAuditSummary(BaseModel):
    """Summary of persisted skill execution audit records."""

    inspect_type: str = "skill_execution_audit"
    path: str
    exists: bool
    total_audit_count: int = Field(ge=0)
    latest_audit_id: str | None
    latest_selected_skill: str | None
    latest_audit_status: str | None
    latest_audit_decision: str | None
    latest_execution_allowed: bool | None
    latest_execution_mode: str | None
    latest_next_action: str | None


class SkillExecutionAuditJsonlStore:
    """Persist skill execution audit records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[SkillExecutionAuditRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(SkillExecutionAuditRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid skill execution audit at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[SkillExecutionAuditRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: SkillExecutionAuditRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_skill_execution_audit(profile: Path) -> dict[str, object]:
    """Build and persist an audit record from the latest controlled gate."""

    gates = ControlledSkillGateJsonlStore(
        profile / CONTROLLED_SKILL_GATE_FILENAME
    ).load()
    if not gates:
        record = _missing_gate_audit(profile)
    else:
        record = _audit_from_gate(profile, gates[-1])
    path = profile / SKILL_EXECUTION_AUDIT_FILENAME
    count = SkillExecutionAuditJsonlStore(path).append(record)
    return {
        "audit_type": "skill_execution_audit",
        "profile_path": str(profile),
        "audit_path": str(path),
        "audit_count": count,
        "audit_record": record.model_dump(mode="json"),
    }


def summarize_skill_execution_audits(path: Path) -> dict[str, object]:
    records = SkillExecutionAuditJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = SkillExecutionAuditSummary(
        path=str(path),
        exists=path.exists(),
        total_audit_count=len(records),
        latest_audit_id=latest.audit_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_audit_status=latest.audit_status if latest else None,
        latest_audit_decision=latest.audit_decision if latest else None,
        latest_execution_allowed=latest.execution_allowed if latest else None,
        latest_execution_mode=latest.execution_mode if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_gate_audit(profile: Path) -> SkillExecutionAuditRecord:
    return SkillExecutionAuditRecord(
        profile_path=str(profile),
        source_gate_id=None,
        selected_skill="controlled_skill_gate_missing",
        selected_action="evaluate_controlled_skill_gate",
        audit_status="blocked",
        audit_decision="audit_blocked",
        execution_allowed=False,
        execution_mode="none",
        audit_stage="pre_execution",
        next_action="evaluate_controlled_skill_gate",
        gate_decision=None,
        gate_confidence=0.0,
        reasons=["controlled_skill_gate_missing"],
    )


def _audit_from_gate(profile: Path, gate) -> SkillExecutionAuditRecord:
    if gate.execution_allowed:
        return _ready_audit(profile, gate)
    if gate.gate_status == "watch":
        return _watch_audit(profile, gate)
    return _blocked_audit(profile, gate)


def _ready_audit(profile: Path, gate) -> SkillExecutionAuditRecord:
    return SkillExecutionAuditRecord(
        profile_path=str(profile),
        source_gate_id=gate.gate_id,
        selected_skill=gate.selected_skill,
        selected_action=gate.selected_action,
        audit_status="ready",
        audit_decision="audit_ready",
        execution_allowed=True,
        execution_mode=gate.execution_mode,
        audit_stage="controlled_staging_audit",
        next_action="create_skill_execution_receipt",
        gate_decision=gate.gate_decision,
        gate_confidence=gate.gate_confidence,
        reasons=["skill_execution_audit_ready"],
    )


def _watch_audit(profile: Path, gate) -> SkillExecutionAuditRecord:
    return SkillExecutionAuditRecord(
        profile_path=str(profile),
        source_gate_id=gate.gate_id,
        selected_skill=gate.selected_skill,
        selected_action=gate.selected_action,
        audit_status="watch",
        audit_decision="audit_watch",
        execution_allowed=False,
        execution_mode="none",
        audit_stage="pre_execution",
        next_action=gate.next_action,
        gate_decision=gate.gate_decision,
        gate_confidence=gate.gate_confidence,
        reasons=["controlled_gate_watch", *gate.reasons],
    )


def _blocked_audit(profile: Path, gate) -> SkillExecutionAuditRecord:
    return SkillExecutionAuditRecord(
        profile_path=str(profile),
        source_gate_id=gate.gate_id,
        selected_skill=gate.selected_skill,
        selected_action=gate.selected_action,
        audit_status="blocked",
        audit_decision="audit_blocked",
        execution_allowed=False,
        execution_mode="none",
        audit_stage="pre_execution",
        next_action=gate.next_action,
        gate_decision=gate.gate_decision,
        gate_confidence=gate.gate_confidence,
        reasons=["controlled_gate_blocked", *gate.reasons],
    )
