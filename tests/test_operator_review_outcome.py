from hex_cortex.memory.operator_review_outcome import (
    record_operator_review_outcome,
    summarize_operator_review_outcomes,
)
from hex_cortex.memory.operator_review_packet import (
    OperatorReviewPacketJsonlStore,
    OperatorReviewPacketRecord,
)


def test_operator_review_outcome_blocks_missing_review(tmp_path) -> None:
    payload = record_operator_review_outcome(tmp_path / "profile")
    record = payload["outcome_record"]

    assert record["outcome_decision"] == "outcome_blocked"
    assert record["outcome_allowed"] is False


def test_operator_review_outcome_auto_needs_registry_activation(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_review(profile, decision="review_watch", approval=False)

    payload = record_operator_review_outcome(profile)
    summary = summarize_operator_review_outcomes(profile / "operator-review-outcome.jsonl")
    record = payload["outcome_record"]

    assert record["requested_outcome"] == "needs_registry_activation"
    assert record["outcome_decision"] == "outcome_needs_registry_activation"
    assert record["next_action"] == "register_or_activate_skill"
    assert summary["latest_outcome_decision"] == "outcome_needs_registry_activation"


def test_operator_review_outcome_approves_ready_review(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_review(profile, decision="review_ready", approval=True)

    payload = record_operator_review_outcome(profile)
    record = payload["outcome_record"]

    assert record["requested_outcome"] == "approved"
    assert record["outcome_decision"] == "outcome_approved"
    assert record["outcome_allowed"] is True


def test_operator_review_outcome_rejects_requested_rejected(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_review(profile, decision="review_ready", approval=True)

    payload = record_operator_review_outcome(profile, requested_outcome="rejected")
    record = payload["outcome_record"]

    assert record["outcome_decision"] == "outcome_rejected"
    assert record["outcome_allowed"] is False


def _write_review(profile, *, decision: str, approval: bool) -> None:
    OperatorReviewPacketJsonlStore(profile / "operator-review-packet.jsonl").append(
        OperatorReviewPacketRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_proposal_gate_id="proposal_a",
            source_score_id="score_a",
            source_summary_id="summary_a",
            proposal_decision="proposal_ready" if approval else "proposal_hold",
            score_decision="score_ready" if approval else "score_hold",
            summary_decision="summary_ready" if approval else "summary_watch",
            review_status="ready" if approval else "watch",
            review_decision=decision,
            review_required=True,
            approval_allowed=approval,
            operator_action=(
                "operator_review_registry_change"
                if approval
                else "register_or_activate_skill"
            ),
            review_confidence=1.0 if approval else 0.2333,
            reasons=["test_review"],
        )
    )
