from hex_cortex.memory.registry_review_dry_run import (
    build_registry_review_dry_run,
    summarize_registry_review_dry_runs,
)
from hex_cortex.memory.registry_review_signature_packet import (
    RegistryReviewSignaturePacketJsonlStore,
    RegistryReviewSignaturePacketRecord,
)
from hex_cortex.memory.skill_registry_review_document import (
    SkillRegistryReviewDocumentJsonlStore,
    SkillRegistryReviewDocumentRecord,
)


def test_registry_review_dry_run_blocks_missing_signature(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_registry_review_dry_run(profile)
    record = payload["dry_run_record"]

    assert record["dry_run_decision"] == "dry_run_blocked"
    assert record["dry_run_allowed"] is False


def test_registry_review_dry_run_watches_more_evidence_signature(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_document(profile, decision="document_needs_registry_activation")
    _write_signature(profile, decision="signature_needs_more_evidence")

    payload = build_registry_review_dry_run(profile)
    summary = summarize_registry_review_dry_runs(
        profile / "registry-review-dry-run.jsonl"
    )
    record = payload["dry_run_record"]

    assert record["dry_run_decision"] == "dry_run_watch"
    assert record["dry_run_allowed"] is False
    assert record["proposed_operation"] == "none"
    assert summary["latest_dry_run_decision"] == "dry_run_watch"


def test_registry_review_dry_run_readies_signed_document(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_document(profile, decision="document_ready")
    _write_signature(profile, decision="signature_signed")

    payload = build_registry_review_dry_run(profile)
    record = payload["dry_run_record"]

    assert record["dry_run_decision"] == "dry_run_ready"
    assert record["dry_run_allowed"] is True
    assert record["proposed_record"]["selected_skill"] == "operator_watch_review"


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


def _write_signature(profile, *, decision: str) -> None:
    is_signed = decision == "signature_signed"
    RegistryReviewSignaturePacketJsonlStore(
        profile / "registry-review-signature-packet.jsonl"
    ).append(
        RegistryReviewSignaturePacketRecord(
            profile_path=str(profile),
            source_document_id="document_a",
            selected_skill="operator_watch_review",
            signer="operator_local",
            requested_signature="signed" if is_signed else "needs_more_evidence",
            document_decision=(
                "document_ready" if is_signed else "document_needs_registry_activation"
            ),
            document_status="ready" if is_signed else "watch",
            registry_action=(
                "confidence_review_only" if is_signed else "manual_activation_review"
            ),
            document_hash="a" * 64,
            signature_status="ready" if is_signed else "watch",
            signature_decision=decision,
            signature_allowed=is_signed,
            next_action=(
                "prepare_registry_review_dry_run"
                if is_signed
                else "prepare_skill_activation_review"
            ),
            reasons=["test_signature"],
        )
    )
