from hex_cortex.memory.registry_review_signature_packet import (
    build_registry_review_signature_packet,
    summarize_registry_review_signature_packets,
)
from hex_cortex.memory.skill_registry_review_document import (
    SkillRegistryReviewDocumentJsonlStore,
    SkillRegistryReviewDocumentRecord,
)


def test_registry_review_signature_blocks_missing_document(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_registry_review_signature_packet(profile)
    record = payload["signature_record"]

    assert record["signature_decision"] == "signature_blocked"
    assert record["signature_allowed"] is False


def test_registry_review_signature_requires_more_evidence(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_document(profile, decision="document_needs_registry_activation")

    payload = build_registry_review_signature_packet(profile)
    summary = summarize_registry_review_signature_packets(
        profile / "registry-review-signature-packet.jsonl"
    )
    record = payload["signature_record"]

    assert record["requested_signature"] == "needs_more_evidence"
    assert record["signature_decision"] == "signature_needs_more_evidence"
    assert record["signature_allowed"] is False
    assert len(record["document_hash"]) == 64
    assert summary["latest_signature_decision"] == "signature_needs_more_evidence"


def test_registry_review_signature_signs_ready_document(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_document(profile, decision="document_ready")

    payload = build_registry_review_signature_packet(profile)
    record = payload["signature_record"]

    assert record["requested_signature"] == "signed"
    assert record["signature_decision"] == "signature_signed"
    assert record["signature_allowed"] is True


def _write_document(profile, *, decision: str) -> None:
    is_ready = decision == "document_ready"
    SkillRegistryReviewDocumentJsonlStore(
        profile / "skill-registry-review-document.jsonl"
    ).append(
        SkillRegistryReviewDocumentRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_outcome_id="outcome_a",
            source_review_id="review_a",
            source_match_id="match_a",
            source_score_id="score_a",
            registry_status="matched" if is_ready else "fallback",
            requested_outcome="approved" if is_ready else "needs_registry_activation",
            outcome_decision=(
                "outcome_approved"
                if is_ready
                else "outcome_needs_registry_activation"
            ),
            review_decision="review_ready" if is_ready else "review_watch",
            score_decision="score_ready" if is_ready else "score_hold",
            document_status="ready" if is_ready else "watch",
            document_decision=decision,
            recommended_operator_decision=(
                "approve_existing_skill_review"
                if is_ready
                else "review_skill_activation"
            ),
            registry_action=(
                "confidence_review_only" if is_ready else "manual_activation_review"
            ),
            next_action=(
                "prepare_operator_signature_packet"
                if is_ready
                else "prepare_skill_activation_review"
            ),
            evidence_lines=["evidence=a", "evidence=b"],
            reasons=["test_document"],
        )
    )
