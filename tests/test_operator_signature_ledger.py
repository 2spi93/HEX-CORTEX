from hex_cortex.memory.operator_signature_ledger import (
    build_operator_signature_ledger,
    summarize_operator_signature_ledgers,
)
from hex_cortex.memory.review_audit_bundle import (
    ReviewAuditBundleJsonlStore,
    ReviewAuditBundleRecord,
)


def test_operator_signature_ledger_blocks_missing_bundle(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_operator_signature_ledger(profile)
    record = payload["ledger_record"]

    assert record["ledger_decision"] == "ledger_blocked"
    assert record["ledger_allowed"] is False
    assert len(record["ledger_hash"]) == 64


def test_operator_signature_ledger_watches_bundle_watch(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_bundle(profile, decision="bundle_watch")

    payload = build_operator_signature_ledger(profile)
    summary = summarize_operator_signature_ledgers(
        profile / "operator-signature-ledger.jsonl"
    )
    record = payload["ledger_record"]

    assert record["ledger_decision"] == "ledger_watch"
    assert record["ledger_allowed"] is False
    assert record["signature_scope"] == "operator_watch_review_bundle"
    assert summary["latest_ledger_decision"] == "ledger_watch"


def test_operator_signature_ledger_readies_bundle_ready(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_bundle(profile, decision="bundle_ready")

    payload = build_operator_signature_ledger(profile)
    record = payload["ledger_record"]

    assert record["ledger_decision"] == "ledger_ready"
    assert record["ledger_allowed"] is True
    assert record["next_action"] == "prepare_review_closeout_report"


def test_operator_signature_ledger_chains_previous_hash(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_bundle(profile, decision="bundle_watch")

    first = build_operator_signature_ledger(profile)["ledger_record"]
    second = build_operator_signature_ledger(profile)["ledger_record"]

    assert second["previous_ledger_hash"] == first["ledger_hash"]


def _write_bundle(profile, *, decision: str) -> None:
    ready = decision == "bundle_ready"
    ReviewAuditBundleJsonlStore(profile / "review-audit-bundle.jsonl").append(
        ReviewAuditBundleRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_signature_id="signature_a",
            source_dry_run_id="dry_run_a",
            source_artifact_id="artifact_a",
            signature_decision="signature_signed" if ready else "signature_needs_more_evidence",
            dry_run_decision="dry_run_ready" if ready else "dry_run_watch",
            artifact_decision="artifact_ready" if ready else "artifact_watch",
            document_hash="a" * 64,
            bundle_hash="b" * 64,
            bundle_status="ready" if ready else "watch",
            bundle_decision=decision,
            bundle_complete=True,
            next_action=(
                "prepare_operator_signature_ledger"
                if ready
                else "prepare_skill_activation_review"
            ),
            reasons=["test_bundle"],
        )
    )
