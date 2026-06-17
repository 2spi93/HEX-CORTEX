"""Operator review packets from proposal, score, and receipt summaries."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.receipt_summary import (
    RECEIPT_SUMMARY_FILENAME,
    ReceiptSummaryJsonlStore,
)
from hex_cortex.memory.registry_update_proposal_gate import (
    REGISTRY_UPDATE_PROPOSAL_GATE_FILENAME,
    RegistryUpdateProposalGateJsonlStore,
)
from hex_cortex.memory.skill_feedback_score import (
    SKILL_FEEDBACK_SCORE_FILENAME,
    SkillFeedbackScoreJsonlStore,
)

OPERATOR_REVIEW_PACKET_FILENAME = "operator-review-packet.jsonl"


class OperatorReviewPacketRecord(BaseModel):
    """One persisted operator review packet."""

    review_id: str = Field(default_factory=lambda: f"operator_review_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_proposal_gate_id: str | None
    source_score_id: str | None
    source_summary_id: str | None
    proposal_decision: str | None
    score_decision: str | None
    summary_decision: str | None
    review_status: str
    review_decision: str
    review_required: bool
    approval_allowed: bool
    operator_action: str
    review_confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


class OperatorReviewPacketSummary(BaseModel):
    """Summary of persisted operator review packets."""

    inspect_type: str = "operator_review_packet"
    path: str
    exists: bool
    total_review_count: int = Field(ge=0)
    latest_review_id: str | None
    latest_selected_skill: str | None
    latest_review_status: str | None
    latest_review_decision: str | None
    latest_review_required: bool | None
    latest_approval_allowed: bool | None
    latest_operator_action: str | None
    latest_review_confidence: float | None


class OperatorReviewPacketJsonlStore:
    """Persist operator review packets as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[OperatorReviewPacketRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(OperatorReviewPacketRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid operator review packet at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[OperatorReviewPacketRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: OperatorReviewPacketRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_operator_review_packet(profile: Path) -> dict[str, object]:
    """Build an operator review packet from latest planning summaries."""

    proposals = RegistryUpdateProposalGateJsonlStore(
        profile / REGISTRY_UPDATE_PROPOSAL_GATE_FILENAME
    ).load()
    scores = SkillFeedbackScoreJsonlStore(
        profile / SKILL_FEEDBACK_SCORE_FILENAME
    ).load()
    summaries = ReceiptSummaryJsonlStore(profile / RECEIPT_SUMMARY_FILENAME).load()
    if not proposals:
        record = _missing_proposal_packet(
            profile,
            scores[-1] if scores else None,
            summaries[-1] if summaries else None,
        )
    else:
        record = _packet_from_sources(
            profile,
            proposals[-1],
            scores[-1] if scores else None,
            summaries[-1] if summaries else None,
        )
    path = profile / OPERATOR_REVIEW_PACKET_FILENAME
    count = OperatorReviewPacketJsonlStore(path).append(record)
    return {
        "review_type": "operator_review_packet",
        "profile_path": str(profile),
        "review_path": str(path),
        "review_count": count,
        "review_record": record.model_dump(mode="json"),
    }


def summarize_operator_review_packets(path: Path) -> dict[str, object]:
    records = OperatorReviewPacketJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = OperatorReviewPacketSummary(
        path=str(path),
        exists=path.exists(),
        total_review_count=len(records),
        latest_review_id=latest.review_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_review_status=latest.review_status if latest else None,
        latest_review_decision=latest.review_decision if latest else None,
        latest_review_required=latest.review_required if latest else None,
        latest_approval_allowed=latest.approval_allowed if latest else None,
        latest_operator_action=latest.operator_action if latest else None,
        latest_review_confidence=latest.review_confidence if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_proposal_packet(profile: Path, score, summary) -> OperatorReviewPacketRecord:
    selected_skill = score.selected_skill if score else "proposal_gate_missing"
    return OperatorReviewPacketRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_proposal_gate_id=None,
        source_score_id=score.score_id if score else None,
        source_summary_id=summary.summary_id if summary else None,
        proposal_decision=None,
        score_decision=score.score_decision if score else None,
        summary_decision=summary.summary_decision if summary else None,
        review_status="blocked",
        review_decision="review_blocked",
        review_required=True,
        approval_allowed=False,
        operator_action="build_registry_review_gate",
        review_confidence=0.0,
        reasons=["registry_review_gate_missing"],
    )


def _packet_from_sources(
    profile: Path,
    proposal,
    score,
    summary,
) -> OperatorReviewPacketRecord:
    confidence = _review_confidence(proposal, score, summary)
    status, decision, required, allowed, action, reasons = _review_outcome(
        proposal,
        score,
        summary,
        confidence,
    )
    return OperatorReviewPacketRecord(
        profile_path=str(profile),
        selected_skill=proposal.selected_skill,
        source_proposal_gate_id=proposal.proposal_gate_id,
        source_score_id=score.score_id if score else None,
        source_summary_id=summary.summary_id if summary else None,
        proposal_decision=proposal.proposal_decision,
        score_decision=score.score_decision if score else None,
        summary_decision=summary.summary_decision if summary else None,
        review_status=status,
        review_decision=decision,
        review_required=required,
        approval_allowed=allowed,
        operator_action=action,
        review_confidence=confidence,
        reasons=reasons,
    )


def _review_confidence(proposal, score, summary) -> float:
    score_value = score.final_score if score else 0.0
    summary_value = summary.summary_score if summary else 0.0
    return round(
        (proposal.proposal_confidence + score_value + summary_value) / 3,
        4,
    )


def _review_outcome(proposal, score, summary, confidence: float):
    if proposal.proposal_allowed and score and score.score_decision == "score_ready":
        summary_ready = summary and summary.summary_decision == "summary_ready"
        if summary_ready and confidence >= 0.8:
            return (
                "ready",
                "review_ready",
                True,
                True,
                "operator_review_registry_change",
                ["operator_review_ready"],
            )
    if proposal.proposal_decision == "proposal_hold":
        return (
            "watch",
            "review_watch",
            True,
            False,
            proposal.next_action,
            ["proposal_hold", *proposal.reasons],
        )
    if score and score.score_decision == "score_hold":
        return (
            "watch",
            "review_watch",
            True,
            False,
            score.next_action,
            ["score_hold", *score.reasons],
        )
    return (
        "blocked",
        "review_blocked",
        True,
        False,
        "repair_operator_review_inputs",
        ["operator_review_inputs_not_ready"],
    )
