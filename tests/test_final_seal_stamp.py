from hex_cortex.memory.final_end_state_certificate import (
    FINAL_END_STATE_CERTIFICATE_FILENAME,
    FinalEndStateCertificateJsonlStore,
    FinalEndStateCertificateRecord,
)
from hex_cortex.memory.final_seal_stamp import (
    FINAL_SEAL_STAMP_FILENAME,
    build_final_seal_stamp,
    summarize_final_seal_stamps,
)


def _write_certificate(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "selected_skill": "operator_watch_review",
        "source_gate_id": "profile_resync_gate_1",
        "source_gate_hash": "a" * 64,
        "source_panel_id": "profile_panel_1",
        "source_resync_decision": "resync_ready",
        "source_gate_decision": "gate_ready",
        "source_panel_display_state": "ready",
        "manual_choice": "accept",
        "safe_to_continue": True,
        "registry_change_applied": False,
        "next_action": "prepare_freeze_stamp",
        "end_state": "READY_AFTER_OPERATOR_ACCEPTANCE",
        "certificate_status": "certified",
        "certificate_decision": "final_end_state_certified",
        "certificate_allowed": True,
        "blocker_count": 0,
        "active_blockers": [],
        "reasons": ["operator_acceptance_propagated", "registry_unchanged"],
        "certificate_hash": "b" * 64,
    }
    payload.update(overrides)
    record = FinalEndStateCertificateRecord(**payload)
    FinalEndStateCertificateJsonlStore(
        profile / FINAL_END_STATE_CERTIFICATE_FILENAME
    ).append(record)
    return record


def test_final_seal_stamp_ready_happy_path(tmp_path) -> None:
    profile = tmp_path / "profile"
    certificate = _write_certificate(profile)

    payload = build_final_seal_stamp(profile)
    record = payload["seal_record"]

    assert record["seal_decision"] == "final_seal_ready"
    assert record["seal_status"] == "ready"
    assert record["seal_allowed"] is True
    assert record["source_certificate_id"] == certificate.certificate_id
    assert record["source_certificate_hash"] == certificate.certificate_hash
    assert record["source_end_state"] == "READY_AFTER_OPERATOR_ACCEPTANCE"
    assert record["safe_to_continue"] is True
    assert record["registry_change_applied"] is False
    assert record["next_action"] == "build_operator_handoff_runbook"
    assert len(record["seal_hash"]) == 64


def test_final_seal_stamp_blocks_missing_certificate(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = build_final_seal_stamp(profile)["seal_record"]

    assert record["seal_allowed"] is False
    assert record["seal_decision"] == "final_seal_blocked"
    assert "final_end_state_certificate_missing" in record["reasons"]
    assert record["next_action"] == "build_final_end_state_certificate"


def test_final_seal_stamp_blocks_uncertified_certificate(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_certificate(
        profile,
        certificate_status="blocked",
        certificate_allowed=False,
        certificate_decision="final_end_state_blocked",
    )

    record = build_final_seal_stamp(profile)["seal_record"]

    assert record["seal_allowed"] is False
    assert "certificate_not_allowed" in record["reasons"]
    assert "certificate_not_certified" in record["reasons"]
    assert "certificate_decision_not_final" in record["reasons"]


def test_final_seal_stamp_blocks_registry_change(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_certificate(profile, registry_change_applied=True)

    record = build_final_seal_stamp(profile)["seal_record"]

    assert record["seal_allowed"] is False
    assert "registry_changed_before_seal" in record["reasons"]


def test_final_seal_stamp_blocks_next_action_mismatch(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_certificate(profile, next_action="rerun_construction_status")

    record = build_final_seal_stamp(profile)["seal_record"]

    assert record["seal_allowed"] is False
    assert "certificate_next_action_not_prepare_freeze_stamp" in record["reasons"]


def test_final_seal_stamp_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_certificate(profile)
    build_final_seal_stamp(profile)

    summary = summarize_final_seal_stamps(profile / FINAL_SEAL_STAMP_FILENAME)

    assert summary["exists"] is True
    assert summary["inspect_type"] == "final_seal_stamp"
    assert summary["total_seal_count"] == 1
    assert summary["latest_source_end_state"] == "READY_AFTER_OPERATOR_ACCEPTANCE"
    assert summary["latest_seal_allowed"] is True
    assert summary["latest_seal_decision"] == "final_seal_ready"
    assert summary["latest_seal_status"] == "ready"
    assert summary["latest_next_action"] == "build_operator_handoff_runbook"
