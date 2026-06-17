from hex_cortex.memory.operator_signature_ledger import (
    OperatorSignatureLedgerJsonlStore,
    OperatorSignatureLedgerRecord,
)
from hex_cortex.memory.review_audit_bundle import (
    ReviewAuditBundleJsonlStore,
    ReviewAuditBundleRecord,
)
from hex_cortex.memory.review_closeout_report import (
    build_review_closeout_report,
    summarize_review_closeout_reports,
)


def test_review_closeout_blocks_missing_ledger(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_review_closeout_report(profile)
    record = payload["closeout_record"]

    assert record["closeout_decision"] == "closeout_blocked"
    assert record["closeout_complete"] is False


def test_review_closeout_watches_ledger_watch(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_bundle(profile, decision="bundle_watch")
    _write_ledger(profile, decision="ledger_watch")

    payload = build_review_closeout_report(profile)
    summary = summarize_review_closeout_reports(
        profile / "review-closeout-report.jsonl"
    )
    record = payload["closeout_record"]

    assert record["closeout_decision"] == "closeout_watch"
    assert record["closeout_complete"] is True
    assert record["operator_next_action"] == "prepare_skill_activation_review"
    assert summary["latest_closeout_decision"] == "closeout_watch"


def test_review_closeout_readies_ledger_ready(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_bundle(profile, decision="bundle_ready")
    _write_ledger(profile, decision="ledger_ready")

    payload = build_review_closeout_report(profile)
    record = payload["closeout_record"]

    assert record["closeout_decision"] == "closeout_ready"
    assert record["closeout_complete"] is True
    assert record["operator_next_action"] == "build_review_archive_index"


def _write_bundle(profile, *, decision: str) -> None:
    ready = decision == "bundle_ready"
    ReviewAuditBundleJsonlStore(profile / "review-audit-bundle.jsonl").append(
        ReviewAuditBundleRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_signature_id="signature_a",
            source_dry_run_id="dry_run_a",
            source_artifact_id="artifact_a",
            signature_decision=(
                "signature_signed" if ready else "signature_needs_more_evidence"
            ),
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


def _write_ledger(profile, *, decision: str) -> None:
    ready = decision == "ledger_ready"
    OperatorSignatureLedgerJsonlStore(profile / "operator-signature-ledger.jsonl").append(
        OperatorSignatureLedgerRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_bundle_id="bundle_a",
            source_bundle_hash="b" * 64,
            previous_ledger_hash=None,
            ledger_hash="c" * 64,
            bundle_decision="bundle_ready" if ready else "bundle_watch",
            bundle_complete=True,
            ledger_status="ready" if ready else "watch",
            ledger_decision=decision,
            ledger_allowed=ready,
            signature_scope=(
                "operator_signed_review_bundle"
                if ready
                else "operator_watch_review_bundle"
            ),
            next_action=(
                "prepare_review_closeout_report"
                if ready
                else "prepare_skill_activation_review"
            ),
            reasons=["test_ledger"],
        )
    )
