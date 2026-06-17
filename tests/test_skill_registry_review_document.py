from hex_cortex.memory.operator_review_outcome import (
    OperatorReviewOutcomeJsonlStore,
    OperatorReviewOutcomeRecord,
)
from hex_cortex.memory.skill_registry_review_document import (
    build_skill_registry_review_document,
    summarize_skill_registry_review_documents,
)


def test_skill_registry_review_document_blocks_missing_outcome(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_skill_registry_review_document(profile)
    summary = summarize_skill_registry_review_documents(
        profile / "skill-registry-review-document.jsonl"
    )
    record = payload["document_record"]

    assert record["document_decision"] == "document_blocked"
    assert record["next_action"] == "record_operator_review_outcome"
    assert summary["latest_document_decision"] == "document_blocked"


def test_skill_registry_review_document_needs_registry_activation(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_outcome(profile, decision="outcome_needs_registry_activation")

    payload = build_skill_registry_review_document(profile)
    record = payload["document_record"]

    assert record["document_decision"] == "document_needs_registry_activation"
    assert record["registry_action"] == "manual_activation_review"
    assert record["next_action"] == "prepare_skill_activation_review"


def test_skill_registry_review_document_rejects_outcome(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_outcome(profile, decision="outcome_rejected")

    payload = build_skill_registry_review_document(profile)
    record = payload["document_record"]

    assert record["document_decision"] == "document_rejected"
    assert record["registry_action"] == "none"


def _write_outcome(profile, *, decision: str) -> None:
    OperatorReviewOutcomeJsonlStore(profile / "operator-review-outcome.jsonl").append(
        OperatorReviewOutcomeRecord(
            profile_path=str(profile),
            source_review_id="review_a",
            selected_skill="operator_watch_review",
            requested_outcome="needs_registry_activation",
            outcome_status="watch" if decision != "outcome_rejected" else "blocked",
            outcome_decision=decision,
            outcome_allowed=False,
            review_decision="review_watch",
            approval_allowed=False,
            operator_action="register_or_activate_skill",
            next_action="register_or_activate_skill",
            reasons=["test_outcome"],
        )
    )
