"""Human-readable skill registry review documents."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.operator_review_outcome import (
    OPERATOR_REVIEW_OUTCOME_FILENAME,
    OperatorReviewOutcomeJsonlStore,
)
from hex_cortex.memory.operator_review_packet import (
    OPERATOR_REVIEW_PACKET_FILENAME,
    OperatorReviewPacketJsonlStore,
)
from hex_cortex.memory.skill_feedback_score import (
    SKILL_FEEDBACK_SCORE_FILENAME,
    SkillFeedbackScoreJsonlStore,
)
from hex_cortex.memory.skill_registry_integration import (
    SKILL_REGISTRY_MATCH_FILENAME,
    SkillRegistryMatchJsonlStore,
)

SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME = "skill-registry-review-document.jsonl"


class SkillRegistryReviewDocumentRecord(BaseModel):
    """One persisted human-readable skill registry review document."""

    document_id: str = Field(default_factory=lambda: f"registry_review_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_outcome_id: str | None
    source_review_id: str | None
    source_match_id: str | None
    source_score_id: str | None
    registry_status: str | None
    requested_outcome: str | None
    outcome_decision: str | None
    review_decision: str | None
    score_decision: str | None
    document_status: str
    document_decision: str
    recommended_operator_decision: str
    registry_action: str
    next_action: str
    evidence_lines: list[str]
    reasons: list[str]


class SkillRegistryReviewDocumentSummary(BaseModel):
    """Summary of persisted skill registry review documents."""

    inspect_type: str = "skill_registry_review_document"
    path: str
    exists: bool
    total_document_count: int = Field(ge=0)
    latest_document_id: str | None
    latest_selected_skill: str | None
    latest_document_status: str | None
    latest_document_decision: str | None
    latest_registry_action: str | None
    latest_next_action: str | None


class SkillRegistryReviewDocumentJsonlStore:
    """Persist skill registry review documents as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[SkillRegistryReviewDocumentRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        SkillRegistryReviewDocumentRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid skill registry review document at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[SkillRegistryReviewDocumentRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: SkillRegistryReviewDocumentRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_skill_registry_review_document(profile: Path) -> dict[str, object]:
    """Build a human-readable skill registry review document."""

    outcomes = OperatorReviewOutcomeJsonlStore(
        profile / OPERATOR_REVIEW_OUTCOME_FILENAME
    ).load()
    reviews = OperatorReviewPacketJsonlStore(
        profile / OPERATOR_REVIEW_PACKET_FILENAME
    ).load()
    matches = SkillRegistryMatchJsonlStore(profile / SKILL_REGISTRY_MATCH_FILENAME).load()
    scores = SkillFeedbackScoreJsonlStore(profile / SKILL_FEEDBACK_SCORE_FILENAME).load()
    if not outcomes:
        record = _missing_outcome_document(
            profile,
            reviews[-1] if reviews else None,
            matches[-1] if matches else None,
            scores[-1] if scores else None,
        )
    else:
        record = _document_from_sources(
            profile,
            outcomes[-1],
            reviews[-1] if reviews else None,
            matches[-1] if matches else None,
            scores[-1] if scores else None,
        )
    path = profile / SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME
    count = SkillRegistryReviewDocumentJsonlStore(path).append(record)
    return {
        "document_type": "skill_registry_review_document",
        "profile_path": str(profile),
        "document_path": str(path),
        "document_count": count,
        "document_record": record.model_dump(mode="json"),
    }


def summarize_skill_registry_review_documents(path: Path) -> dict[str, object]:
    records = SkillRegistryReviewDocumentJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = SkillRegistryReviewDocumentSummary(
        path=str(path),
        exists=path.exists(),
        total_document_count=len(records),
        latest_document_id=latest.document_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_document_status=latest.document_status if latest else None,
        latest_document_decision=latest.document_decision if latest else None,
        latest_registry_action=latest.registry_action if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_outcome_document(profile: Path, review, match, score):
    selected_skill = _selected_skill(review, match, score, "operator_outcome_missing")
    return SkillRegistryReviewDocumentRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_outcome_id=None,
        source_review_id=review.review_id if review else None,
        source_match_id=match.match_id if match else None,
        source_score_id=score.score_id if score else None,
        registry_status=match.registry_status if match else None,
        requested_outcome=None,
        outcome_decision=None,
        review_decision=review.review_decision if review else None,
        score_decision=score.score_decision if score else None,
        document_status="blocked",
        document_decision="document_blocked",
        recommended_operator_decision="build_operator_review_outcome",
        registry_action="none",
        next_action="record_operator_review_outcome",
        evidence_lines=["operator review outcome is missing"],
        reasons=["operator_review_outcome_missing"],
    )


def _document_from_sources(profile: Path, outcome, review, match, score):
    status, decision, operator_decision, action, next_action, reasons = _document_decision(
        outcome,
        match,
        score,
    )
    return SkillRegistryReviewDocumentRecord(
        profile_path=str(profile),
        selected_skill=outcome.selected_skill,
        source_outcome_id=outcome.outcome_id,
        source_review_id=review.review_id if review else outcome.source_review_id,
        source_match_id=match.match_id if match else None,
        source_score_id=score.score_id if score else None,
        registry_status=match.registry_status if match else None,
        requested_outcome=outcome.requested_outcome,
        outcome_decision=outcome.outcome_decision,
        review_decision=review.review_decision if review else outcome.review_decision,
        score_decision=score.score_decision if score else None,
        document_status=status,
        document_decision=decision,
        recommended_operator_decision=operator_decision,
        registry_action=action,
        next_action=next_action,
        evidence_lines=_evidence_lines(outcome, review, match, score),
        reasons=reasons,
    )


def _selected_skill(review, match, score, fallback: str) -> str:
    if review:
        return review.selected_skill
    if match:
        return match.latent_suggested_skill
    if score:
        return score.selected_skill
    return fallback


def _document_decision(outcome, match, score):
    registry_status = match.registry_status if match else None
    score_decision = score.score_decision if score else None
    if outcome.outcome_decision == "outcome_approved" and outcome.outcome_allowed:
        if registry_status == "matched" and score_decision == "score_ready":
            return (
                "ready",
                "document_ready",
                "approve_existing_skill_review",
                "confidence_review_only",
                "prepare_operator_signature_packet",
                ["approved_existing_skill_review"],
            )
        return (
            "watch",
            "document_needs_registry_activation",
            "review_skill_activation",
            "manual_activation_review",
            "prepare_skill_activation_review",
            ["approval_requires_registry_activation"],
        )
    if outcome.outcome_decision == "outcome_needs_registry_activation":
        return (
            "watch",
            "document_needs_registry_activation",
            "review_skill_activation",
            "manual_activation_review",
            "prepare_skill_activation_review",
            ["operator_outcome_requires_registry_activation"],
        )
    if outcome.outcome_decision == "outcome_deferred":
        return (
            "watch",
            "document_deferred",
            "defer_skill_review",
            "none",
            outcome.next_action,
            ["operator_review_deferred"],
        )
    return (
        "blocked",
        "document_rejected",
        "reject_skill_review",
        "none",
        "repair_operator_review_inputs",
        ["operator_review_rejected_or_blocked"],
    )


def _evidence_lines(outcome, review, match, score) -> list[str]:
    lines = [
        f"outcome_decision={outcome.outcome_decision}",
        f"requested_outcome={outcome.requested_outcome}",
        f"outcome_allowed={outcome.outcome_allowed}",
    ]
    if review:
        lines.append(f"review_decision={review.review_decision}")
        lines.append(f"approval_allowed={review.approval_allowed}")
    if match:
        lines.append(f"registry_status={match.registry_status}")
        lines.append(f"match_score={match.match_score}")
    if score:
        lines.append(f"score_decision={score.score_decision}")
        lines.append(f"final_score={score.final_score}")
    return lines
