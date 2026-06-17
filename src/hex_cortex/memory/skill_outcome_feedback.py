"""Outcome feedback records for audited skill staging."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.skill_execution_audit import (
    SKILL_EXECUTION_AUDIT_FILENAME,
    SkillExecutionAuditJsonlStore,
)

SKILL_OUTCOME_FEEDBACK_FILENAME = "skill-outcome-feedback.jsonl"
ALLOWED_OUTCOMES = {"not_observed", "blocked", "success", "failure", "regression"}


class SkillOutcomeFeedbackRecord(BaseModel):
    """One persisted skill outcome feedback record."""

    feedback_id: str = Field(default_factory=lambda: f"skill_feedback_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_audit_id: str | None
    selected_skill: str
    selected_action: str
    audit_decision: str | None
    execution_allowed: bool
    observed_outcome: str
    outcome_score: float = Field(ge=0.0, le=1.0)
    feedback_status: str
    feedback_decision: str
    next_action: str
    reasons: list[str]


class SkillOutcomeFeedbackSummary(BaseModel):
    """Summary of persisted skill outcome feedback records."""

    inspect_type: str = "skill_outcome_feedback"
    path: str
    exists: bool
    total_feedback_count: int = Field(ge=0)
    latest_feedback_id: str | None
    latest_selected_skill: str | None
    latest_observed_outcome: str | None
    latest_feedback_status: str | None
    latest_feedback_decision: str | None
    latest_next_action: str | None
    latest_outcome_score: float | None


class SkillOutcomeFeedbackJsonlStore:
    """Persist skill outcome feedback as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[SkillOutcomeFeedbackRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(SkillOutcomeFeedbackRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid skill outcome feedback at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[SkillOutcomeFeedbackRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: SkillOutcomeFeedbackRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def record_skill_outcome_feedback(
    profile: Path,
    *,
    observed_outcome: str = "not_observed",
) -> dict[str, object]:
    """Record outcome feedback from the latest skill execution audit."""

    if observed_outcome not in ALLOWED_OUTCOMES:
        raise ValueError(f"unsupported skill outcome: {observed_outcome}")
    audits = SkillExecutionAuditJsonlStore(
        profile / SKILL_EXECUTION_AUDIT_FILENAME
    ).load()
    if not audits:
        record = _missing_audit_feedback(profile, observed_outcome)
    else:
        record = _feedback_from_audit(profile, audits[-1], observed_outcome)
    path = profile / SKILL_OUTCOME_FEEDBACK_FILENAME
    count = SkillOutcomeFeedbackJsonlStore(path).append(record)
    return {
        "feedback_type": "skill_outcome_feedback",
        "profile_path": str(profile),
        "feedback_path": str(path),
        "feedback_count": count,
        "feedback_record": record.model_dump(mode="json"),
    }


def summarize_skill_outcome_feedback(path: Path) -> dict[str, object]:
    records = SkillOutcomeFeedbackJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = SkillOutcomeFeedbackSummary(
        path=str(path),
        exists=path.exists(),
        total_feedback_count=len(records),
        latest_feedback_id=latest.feedback_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_observed_outcome=latest.observed_outcome if latest else None,
        latest_feedback_status=latest.feedback_status if latest else None,
        latest_feedback_decision=latest.feedback_decision if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_outcome_score=latest.outcome_score if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_audit_feedback(
    profile: Path,
    observed_outcome: str,
) -> SkillOutcomeFeedbackRecord:
    return SkillOutcomeFeedbackRecord(
        profile_path=str(profile),
        source_audit_id=None,
        selected_skill="skill_execution_audit_missing",
        selected_action="build_skill_execution_audit",
        audit_decision=None,
        execution_allowed=False,
        observed_outcome=observed_outcome,
        outcome_score=0.0,
        feedback_status="blocked",
        feedback_decision="feedback_blocked",
        next_action="build_skill_execution_audit",
        reasons=["skill_execution_audit_missing"],
    )


def _feedback_from_audit(
    profile: Path,
    audit,
    observed_outcome: str,
) -> SkillOutcomeFeedbackRecord:
    outcome_score = _outcome_score(audit, observed_outcome)
    status, decision, next_action, reasons = _outcome_decision(audit, observed_outcome)
    return SkillOutcomeFeedbackRecord(
        profile_path=str(profile),
        source_audit_id=audit.audit_id,
        selected_skill=audit.selected_skill,
        selected_action=audit.selected_action,
        audit_decision=audit.audit_decision,
        execution_allowed=audit.execution_allowed,
        observed_outcome=observed_outcome,
        outcome_score=outcome_score,
        feedback_status=status,
        feedback_decision=decision,
        next_action=next_action,
        reasons=reasons,
    )


def _outcome_score(audit, observed_outcome: str) -> float:
    if observed_outcome == "success" and audit.execution_allowed:
        return 1.0
    if observed_outcome == "not_observed" and not audit.execution_allowed:
        return 0.7
    if observed_outcome == "blocked":
        return 0.6
    if observed_outcome == "failure":
        return 0.2
    if observed_outcome == "regression":
        return 0.0
    return 0.4


def _outcome_decision(audit, observed_outcome: str):
    if not audit.execution_allowed:
        return (
            "watch",
            "feedback_watch",
            audit.next_action,
            ["audit_not_execution_allowed", *audit.reasons],
        )
    if observed_outcome == "success":
        return (
            "ready",
            "feedback_success",
            "promote_skill_confidence_candidate",
            ["skill_outcome_success"],
        )
    if observed_outcome in {"failure", "regression"}:
        return (
            "blocked",
            "feedback_blocked",
            "repair_skill_or_gate",
            [f"skill_outcome_{observed_outcome}"],
        )
    return (
        "watch",
        "feedback_watch",
        "observe_skill_outcome",
        ["skill_outcome_not_observed"],
    )
