from hex_cortex.memory.final_end_state_certificate import (
    FINAL_END_STATE_CERTIFICATE_FILENAME,
    FinalEndStateCertificateJsonlStore,
    FinalEndStateCertificateRecord,
)
from hex_cortex.memory.final_freeze_stamp import (
    FINAL_FREEZE_STAMP_FILENAME,
    build_final_freeze_stamp,
    summarize_final_freeze_stamps,
)


def _write_certificate(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "selected_skill": "operator_watch_review",
        "source_gate_id": "profile_resync_gate_ready_1",
        "source_gate_hash": "a" * 64,
        "source_panel_id": "profile_panel_ready_1",
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
        "reasons": ["registry_unchanged"],
        "certificate_hash": "b" * 64,
    }
    payload.update(overrides)
    record = FinalEndStateCertificateRecord(**payload)
    FinalEndStateCertificateJsonlStore(
        profile / FINAL_END_STATE_CERTIFICATE_FILENAME
    ).append(record)
    return record


def test_final_freeze_stamp_ready_happy_path(tmp_path) -> None:
    profile = tmp_path / "profile"
    certificate = _write_certificate(profile)

    payload = build_final_freeze_stamp(profile)
    record = payload["stamp_record"]

    assert record["stamp_status"] == "ready"
    assert record["stamp_decision"] == "final_stamp_ready"
    assert record["stamp_allowed"] is True
    assert record["next_action"] == "build_operator_handoff_runbook"
    assert record["source_certificate_id"] == certificate.certificate_id
    assert record["source_certificate_hash"] == certificate.certificate_hash
    assert record["source_end_state"] == "READY_AFTER_OPERATOR_ACCEPTANCE"
    assert record["safe_to_continue"] is True
    assert record["registry_change_applied"] is False
    assert len(record["stamp_hash"]) == 64


def test_final_freeze_stamp_blocks_missing_certificate(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = build_final_freeze_stamp(profile)["stamp_record"]

    assert record["stamp_allowed"] is False
    assert record["stamp_decision"] == "final_stamp_blocked"
    assert "final_end_state_certificate_missing" in record["reasons"]


def test_final_freeze_stamp_blocks_when_certificate_not_certified(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_certificate(profile, certificate_status="blocked")

    record = build_final_freeze_stamp(profile)["stamp_record"]

    assert record["stamp_allowed"] is False
    assert "certificate_not_certified" in record["reasons"]


def test_final_freeze_stamp_blocks_when_registry_changed(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_certificate(profile, registry_change_applied=True)

    record = build_final_freeze_stamp(profile)["stamp_record"]

    assert record["stamp_allowed"] is False
    assert "registry_changed_before_stamp" in record["reasons"]


def test_final_freeze_stamp_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_certificate(profile)
    build_final_freeze_stamp(profile)

    summary = summarize_final_freeze_stamps(profile / FINAL_FREEZE_STAMP_FILENAME)

    assert summary["exists"] is True
    assert summary["inspect_type"] == "final_freeze_stamp"
    assert summary["total_stamp_count"] == 1
    assert summary["latest_stamp_status"] == "ready"
    assert summary["latest_stamp_decision"] == "final_stamp_ready"
    assert summary["latest_stamp_allowed"] is True
    assert summary["latest_next_action"] == "build_operator_handoff_runbook"
    assert summary["latest_source_end_state"] == "READY_AFTER_OPERATOR_ACCEPTANCE"
