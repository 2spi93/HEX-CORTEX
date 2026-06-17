from hex_cortex.memory.registry_review_dry_run import (
    RegistryReviewDryRunJsonlStore,
    RegistryReviewDryRunRecord,
)
from hex_cortex.memory.registry_review_signature_packet import (
    RegistryReviewSignaturePacketJsonlStore,
    RegistryReviewSignaturePacketRecord,
)
from hex_cortex.memory.review_activation_artifact import (
    ReviewActivationArtifactJsonlStore,
    ReviewActivationArtifactRecord,
)
from hex_cortex.memory.review_audit_bundle import (
    build_review_audit_bundle,
    summarize_review_audit_bundles,
)


def test_review_audit_bundle_blocks_missing_sources(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_review_audit_bundle(profile)
    record = payload["bundle_record"]

    assert record["bundle_decision"] == "bundle_blocked"
    assert record["bundle_complete"] is False


def test_review_audit_bundle_watches_artifact_watch(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_sources(profile, ready=False)

    payload = build_review_audit_bundle(profile)
    summary = summarize_review_audit_bundles(profile / "review-audit-bundle.jsonl")
    record = payload["bundle_record"]

    assert record["bundle_decision"] == "bundle_watch"
    assert record["bundle_complete"] is True
    assert len(record["bundle_hash"]) == 64
    assert summary["latest_bundle_decision"] == "bundle_watch"


def test_review_audit_bundle_readies_artifact_ready(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_sources(profile, ready=True)

    payload = build_review_audit_bundle(profile)
    record = payload["bundle_record"]

    assert record["bundle_decision"] == "bundle_ready"
    assert record["bundle_complete"] is True
    assert record["next_action"] == "prepare_operator_signature_ledger"


def _write_sources(profile, *, ready: bool) -> None:
    document_hash = "a" * 64
    RegistryReviewSignaturePacketJsonlStore(
        profile / "registry-review-signature-packet.jsonl"
    ).append(
        RegistryReviewSignaturePacketRecord(
            profile_path=str(profile),
            source_document_id="document_a",
            selected_skill="operator_watch_review",
            signer="operator_local",
            requested_signature="signed" if ready else "needs_more_evidence",
            document_decision="document_ready" if ready else "document_needs_registry_activation",
            document_status="ready" if ready else "watch",
            registry_action="confidence_review_only" if ready else "manual_activation_review",
            document_hash=document_hash,
            signature_status="ready" if ready else "watch",
            signature_decision="signature_signed" if ready else "signature_needs_more_evidence",
            signature_allowed=ready,
            next_action=(
                "prepare_registry_review_dry_run"
                if ready
                else "prepare_skill_activation_review"
            ),
            reasons=["test_signature"],
        )
    )
    RegistryReviewDryRunJsonlStore(profile / "registry-review-dry-run.jsonl").append(
        RegistryReviewDryRunRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_signature_id="signature_a",
            source_document_id="document_a",
            signer="operator_local",
            signature_decision="signature_signed" if ready else "signature_needs_more_evidence",
            signature_allowed=ready,
            document_decision="document_ready" if ready else "document_needs_registry_activation",
            registry_action="confidence_review_only" if ready else "manual_activation_review",
            document_hash=document_hash,
            dry_run_status="ready" if ready else "watch",
            dry_run_decision="dry_run_ready" if ready else "dry_run_watch",
            dry_run_allowed=ready,
            proposed_operation="skill_confidence_review" if ready else "none",
            proposed_record={"selected_skill": "operator_watch_review"} if ready else {},
            next_action=(
                "prepare_registry_activation_artifact"
                if ready
                else "prepare_skill_activation_review"
            ),
            reasons=["test_dry_run"],
        )
    )
    ReviewActivationArtifactJsonlStore(
        profile / "review-activation-artifact.jsonl"
    ).append(
        ReviewActivationArtifactRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_dry_run_id="dry_run_a",
            source_document_id="document_a",
            document_hash=document_hash,
            dry_run_decision="dry_run_ready" if ready else "dry_run_watch",
            dry_run_allowed=ready,
            proposed_operation="skill_confidence_review" if ready else "none",
            artifact_status="ready" if ready else "watch",
            artifact_decision="artifact_ready" if ready else "artifact_watch",
            artifact_allowed=ready,
            artifact_kind="skill_confidence_review" if ready else "manual_review_required",
            artifact_payload={"selected_skill": "operator_watch_review"},
            next_action=(
                "prepare_operator_signature_ledger"
                if ready
                else "prepare_skill_activation_review"
            ),
            reasons=["test_artifact"],
        )
    )
