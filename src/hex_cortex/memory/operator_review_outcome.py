"""Operator review outcomes for human-facing review packets."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.operator_review_packet import (
    OPERATOR_REVIEW_PACKET_FILENAME,
    OperatorReviewPacketJsonlStore,
)

OPERATOR_REVIEW_OUTCOME_FILENAME = "operator-review-outcome.jsonl"
ALLOWED_OPERATOR_OUTCOMES = {
    "auto",
    "approved",
    "rejected",
    "deferred",
    "needs_registry_activation",
}


class OperatorReviewOutcomeRecord(BaseModel):
    """One persisted operator review outcome."""

    outcome_id: str = Field(default_factory=lambda: f"operator_outcome_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_review_id: str | None
    selected_skill: str
    requested_outcome: str
    outcome_status: str
    outcome_decision: str
    outcome_allowed: bool
    review_decision: str | None
    approval_allowed: bool
    operator_action: str
    next_action: str
    reasons: list[str]


class OperatorReviewOutcomeSummary(BaseModel):
    """Summary of persisted operator review outcomes."""

    inspect_type: str = "operator_review_outcome"
    path: str
    exists: bool
    total_outcome_count: int = Field(ge=0)
    latest_outcome_id: str | None
    latest_selected_skill: str | None
    latest_requested_outcome: str | None
    latest_outcome_status: str | None
    latest_outcome_decision: str | None
    latest_outcome_allowed: bool | None
    latest_next_action: str | None


class OperatorReviewOutcomeJsonlStore:
    """Persist operator review outcomes as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[OperatorReviewOutcomeRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(OperatorReviewOutcomeRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid operator review outcome at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[OperatorReviewOutcomeRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: OperatorReviewOutcomeRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def record_operator_review_outcome(
    profile: Path,
    *,
    requested_outcome: str = "auto",
) -> dict[str, object]:
    """Record an operator outcome from the latest review packet."""

    if requested_outcome not in ALLOWED_OPERATOR_OUTCOMES:
        raise ValueError(f"unsupported operator review outcome: {requested_outcome}")
    reviews = OperatorReviewPacketJsonlStore(
        profile / OPERATOR_REVIEW_PACKET_FILENAME
    ).load()
    if not reviews:
        record = _missing_review_outcome(profile, requested_outcome)
    else:
        record = _outcome_from_review(profile, reviews[-1], requested_outcome)
    path = profile / OPERATOR_REVIEW_OUTCOME_FILENAME
    count = OperatorReviewOutcomeJsonlStore(path).append(record)
    return {
        "outcome_type": "operator_review_outcome",
        "profile_path": str(profile),
        "outcome_path": str(path),
        "outcome_count": count,
        "outcome_record": record.model_dump(mode="json"),
    }


def summarize_operator_review_outcomes(path: Path) -> dict[str, object]:
    records = OperatorReviewOutcomeJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = OperatorReviewOutcomeSummary(
        path=str(path),
        exists=path.exists(),
        total_outcome_count=len(records),
        latest_outcome_id=latest.outcome_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_requested_outcome=latest.requested_outcome if latest else None,
        latest_outcome_status=latest.outcome_status if latest else None,
        latest_outcome_decision=latest.outcome_decision if latest else None,
        latest_outcome_allowed=latest.outcome_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_review_outcome(
    profile: Path,
    requested_outcome: str,
) -> OperatorReviewOutcomeRecord:
    return OperatorReviewOutcomeRecord(
        profile_path=str(profile),
        source_review_id=None,
        selected_skill="operator_review_packet_missing",
        requested_outcome=requested_outcome,
        outcome_status="blocked",
        outcome_decision="outcome_blocked",
        outcome_allowed=False,
        review_decision=None,
        approval_allowed=False,
        operator_action="build_operator_review_packet",
        next_action="build_operator_review_packet",
        reasons=["operator_review_packet_missing"],
    )


def _outcome_from_review(
    profile: Path,
    review,
    requested_outcome: str,
) -> OperatorReviewOutcomeRecord:
    effective = _effective_outcome(review, requested_outcome)
    status, decision, allowed, next_action, reasons = _decision_from_effective(
        review,
        effective,
    )
    return OperatorReviewOutcomeRecord(
        profile_path=str(profile),
        source_review_id=review.review_id,
        selected_skill=review.selected_skill,
        requested_outcome=effective,
        outcome_status=status,
        outcome_decision=decision,
        outcome_allowed=allowed,
        review_decision=review.review_decision,
        approval_allowed=review.approval_allowed,
        operator_action=review.operator_action,
        next_action=next_action,
        reasons=reasons,
    )


def _effective_outcome(review, requested_outcome: str) -> str:
    if requested_outcome != "auto":
        return requested_outcome
    if review.approval_allowed and review.review_decision == "review_ready":
        return "approved"
    if review.operator_action == "register_or_activate_skill":
        return "needs_registry_activation"
    if review.review_decision == "review_watch":
        return "deferred"
    return "rejected"


def _decision_from_effective(review, effective: str):
    if effective == "approved" and review.approval_allowed:
        return (
            "ready",
            "outcome_approved",
            True,
            "prepare_registry_review_document",
            ["operator_approved_ready_review"],
        )
    if effective == "needs_registry_activation":
        return (
            "watch",
            "outcome_needs_registry_activation",
            False,
            "register_or_activate_skill",
            ["operator_outcome_requires_registry_activation"],
        )
    if effective == "deferred":
        return (
            "watch",
            "outcome_deferred",
            False,
            review.operator_action,
            ["operator_deferred_review"],
        )
    return (
        "blocked",
        "outcome_rejected",
        False,
        "repair_operator_review_inputs",
        ["operator_rejected_review"],
    )
