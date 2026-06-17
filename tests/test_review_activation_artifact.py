from hex_cortex.memory.registry_review_dry_run import (
    RegistryReviewDryRunJsonlStore,
    RegistryReviewDryRunRecord,
)
from hex_cortex.memory.review_activation_artifact import (
    build_review_activation_artifact,
    summarize_review_activation_artifacts,
)


def test_review_activation_artifact_blocks_missing_dry_run(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_review_activation_artifact(profile)
    record = payload["artifact_record"]

    assert record["artifact_decision"] == "artifact_blocked"
    assert record["artifact_allowed"] is False


def test_review_activation_artifact_watches_not_allowed_dry_run(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_dry_run(profile, allowed=False)

    payload = build_review_activation_artifact(profile)
    summary = summarize_review_activation_artifacts(
        profile / "review-activation-artifact.jsonl"
    )
    record = payload["artifact_record"]

    assert record["artifact_decision"] == "artifact_watch"
    assert record["artifact_allowed"] is False
    assert record["artifact_payload"]["required_action"] == "prepare_skill_activation_review"
    assert summary["latest_artifact_decision"] == "artifact_watch"


def test_review_activation_artifact_readies_allowed_dry_run(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_dry_run(profile, allowed=True)

    payload = build_review_activation_artifact(profile)
    record = payload["artifact_record"]

    assert record["artifact_decision"] == "artifact_ready"
    assert record["artifact_allowed"] is True
    assert record["next_action"] == "prepare_operator_signature_ledger"


def _write_dry_run(profile, *, allowed: bool) -> None:
    RegistryReviewDryRunJsonlStore(profile / "registry-review-dry-run.jsonl").append(
        RegistryReviewDryRunRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_signature_id="signature_a",
            source_document_id="document_a",
            signer="operator_local",
            signature_decision="signature_signed" if allowed else "signature_needs_more_evidence",
            signature_allowed=allowed,
            document_decision="document_ready" if allowed else "document_needs_registry_activation",
            registry_action="confidence_review_only" if allowed else "manual_activation_review",
            document_hash="a" * 64,
            dry_run_status="ready" if allowed else "watch",
            dry_run_decision="dry_run_ready" if allowed else "dry_run_watch",
            dry_run_allowed=allowed,
            proposed_operation="skill_confidence_review" if allowed else "none",
            proposed_record={"selected_skill": "operator_watch_review"} if allowed else {},
            next_action=(
                "prepare_registry_activation_artifact"
                if allowed
                else "prepare_skill_activation_review"
            ),
            reasons=["test_dry_run"],
        )
    )
