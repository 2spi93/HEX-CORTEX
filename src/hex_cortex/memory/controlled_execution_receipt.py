"""Controlled execution receipts for audited skill staging."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.skill_execution_audit import (
    SKILL_EXECUTION_AUDIT_FILENAME,
    SkillExecutionAuditJsonlStore,
)
from hex_cortex.memory.skill_outcome_feedback import (
    SKILL_OUTCOME_FEEDBACK_FILENAME,
    SkillOutcomeFeedbackJsonlStore,
)

CONTROLLED_EXECUTION_RECEIPT_FILENAME = "controlled-execution-receipt.jsonl"


class ControlledExecutionReceiptRecord(BaseModel):
    """One persisted controlled execution receipt."""

    receipt_id: str = Field(default_factory=lambda: f"execution_receipt_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_audit_id: str | None
    source_feedback_id: str | None
    selected_skill: str
    selected_action: str
    receipt_status: str
    receipt_decision: str
    execution_allowed: bool
    execution_observed: bool
    execution_mode: str
    observed_outcome: str | None
    certification: str
    next_action: str
    reasons: list[str]


class ControlledExecutionReceiptSummary(BaseModel):
    """Summary of persisted controlled execution receipts."""

    inspect_type: str = "controlled_execution_receipt"
    path: str
    exists: bool
    total_receipt_count: int = Field(ge=0)
    latest_receipt_id: str | None
    latest_selected_skill: str | None
    latest_receipt_status: str | None
    latest_receipt_decision: str | None
    latest_execution_allowed: bool | None
    latest_execution_observed: bool | None
    latest_certification: str | None
    latest_next_action: str | None


class ControlledExecutionReceiptJsonlStore:
    """Persist controlled execution receipts as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ControlledExecutionReceiptRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ControlledExecutionReceiptRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid controlled execution receipt at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ControlledExecutionReceiptRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ControlledExecutionReceiptRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_controlled_execution_receipt(profile: Path) -> dict[str, object]:
    """Build a receipt certifying the latest controlled execution state."""

    audits = SkillExecutionAuditJsonlStore(
        profile / SKILL_EXECUTION_AUDIT_FILENAME
    ).load()
    feedback = SkillOutcomeFeedbackJsonlStore(
        profile / SKILL_OUTCOME_FEEDBACK_FILENAME
    ).load()
    if not audits:
        record = _missing_audit_receipt(profile, feedback[-1] if feedback else None)
    else:
        record = _receipt_from_sources(
            profile,
            audits[-1],
            feedback[-1] if feedback else None,
        )
    path = profile / CONTROLLED_EXECUTION_RECEIPT_FILENAME
    count = ControlledExecutionReceiptJsonlStore(path).append(record)
    return {
        "receipt_type": "controlled_execution_receipt",
        "profile_path": str(profile),
        "receipt_path": str(path),
        "receipt_count": count,
        "receipt_record": record.model_dump(mode="json"),
    }


def summarize_controlled_execution_receipts(path: Path) -> dict[str, object]:
    records = ControlledExecutionReceiptJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ControlledExecutionReceiptSummary(
        path=str(path),
        exists=path.exists(),
        total_receipt_count=len(records),
        latest_receipt_id=latest.receipt_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_receipt_status=latest.receipt_status if latest else None,
        latest_receipt_decision=latest.receipt_decision if latest else None,
        latest_execution_allowed=latest.execution_allowed if latest else None,
        latest_execution_observed=latest.execution_observed if latest else None,
        latest_certification=latest.certification if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_audit_receipt(profile: Path, feedback) -> ControlledExecutionReceiptRecord:
    return ControlledExecutionReceiptRecord(
        profile_path=str(profile),
        source_audit_id=None,
        source_feedback_id=feedback.feedback_id if feedback else None,
        selected_skill="skill_execution_audit_missing",
        selected_action="build_skill_execution_audit",
        receipt_status="blocked",
        receipt_decision="receipt_blocked",
        execution_allowed=False,
        execution_observed=False,
        execution_mode="none",
        observed_outcome=feedback.observed_outcome if feedback else None,
        certification="execution_not_certified",
        next_action="build_skill_execution_audit",
        reasons=["skill_execution_audit_missing"],
    )


def _receipt_from_sources(
    profile: Path,
    audit,
    feedback,
) -> ControlledExecutionReceiptRecord:
    if not audit.execution_allowed:
        return _not_executed_receipt(profile, audit, feedback)
    if feedback and feedback.observed_outcome == "success":
        return _success_receipt(profile, audit, feedback)
    if feedback and feedback.observed_outcome in {"failure", "regression"}:
        return _failed_receipt(profile, audit, feedback)
    return _staged_unobserved_receipt(profile, audit, feedback)


def _not_executed_receipt(
    profile: Path,
    audit,
    feedback,
) -> ControlledExecutionReceiptRecord:
    return ControlledExecutionReceiptRecord(
        profile_path=str(profile),
        source_audit_id=audit.audit_id,
        source_feedback_id=feedback.feedback_id if feedback else None,
        selected_skill=audit.selected_skill,
        selected_action=audit.selected_action,
        receipt_status="watch",
        receipt_decision="receipt_not_executed",
        execution_allowed=False,
        execution_observed=False,
        execution_mode="none",
        observed_outcome=feedback.observed_outcome if feedback else None,
        certification="execution_prevented_by_audit",
        next_action=audit.next_action,
        reasons=["audit_execution_not_allowed", *audit.reasons],
    )


def _success_receipt(
    profile: Path,
    audit,
    feedback,
) -> ControlledExecutionReceiptRecord:
    return ControlledExecutionReceiptRecord(
        profile_path=str(profile),
        source_audit_id=audit.audit_id,
        source_feedback_id=feedback.feedback_id,
        selected_skill=audit.selected_skill,
        selected_action=audit.selected_action,
        receipt_status="ready",
        receipt_decision="receipt_success",
        execution_allowed=True,
        execution_observed=True,
        execution_mode=audit.execution_mode,
        observed_outcome=feedback.observed_outcome,
        certification="controlled_execution_success_observed",
        next_action="prepare_registry_learning_candidate",
        reasons=["controlled_execution_success"],
    )


def _failed_receipt(
    profile: Path,
    audit,
    feedback,
) -> ControlledExecutionReceiptRecord:
    return ControlledExecutionReceiptRecord(
        profile_path=str(profile),
        source_audit_id=audit.audit_id,
        source_feedback_id=feedback.feedback_id,
        selected_skill=audit.selected_skill,
        selected_action=audit.selected_action,
        receipt_status="blocked",
        receipt_decision="receipt_failure",
        execution_allowed=True,
        execution_observed=True,
        execution_mode=audit.execution_mode,
        observed_outcome=feedback.observed_outcome,
        certification="controlled_execution_failure_observed",
        next_action="repair_skill_or_gate",
        reasons=["controlled_execution_failed"],
    )


def _staged_unobserved_receipt(
    profile: Path,
    audit,
    feedback,
) -> ControlledExecutionReceiptRecord:
    return ControlledExecutionReceiptRecord(
        profile_path=str(profile),
        source_audit_id=audit.audit_id,
        source_feedback_id=feedback.feedback_id if feedback else None,
        selected_skill=audit.selected_skill,
        selected_action=audit.selected_action,
        receipt_status="watch",
        receipt_decision="receipt_staged_unobserved",
        execution_allowed=True,
        execution_observed=False,
        execution_mode=audit.execution_mode,
        observed_outcome=feedback.observed_outcome if feedback else None,
        certification="controlled_execution_not_observed",
        next_action="observe_skill_outcome",
        reasons=["controlled_execution_staged_without_outcome"],
    )
