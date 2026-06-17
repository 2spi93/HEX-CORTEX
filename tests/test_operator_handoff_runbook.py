from hex_cortex.memory.final_seal_stamp import (
    FINAL_SEAL_STAMP_FILENAME,
    FinalSealStampJsonlStore,
    FinalSealStampRecord,
)
from hex_cortex.memory.operator_handoff_runbook import (
    OPERATOR_HANDOFF_RUNBOOK_FILENAME,
    build_operator_handoff_runbook,
    summarize_operator_handoff_runbooks,
)


def _write_seal(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "selected_skill": "operator_watch_review",
        "source_certificate_id": "final_end_state_certificate_1",
        "source_certificate_hash": "a" * 64,
        "source_end_state": "READY_AFTER_OPERATOR_ACCEPTANCE",
        "safe_to_continue": True,
        "registry_change_applied": False,
        "seal_status": "ready",
        "seal_decision": "final_seal_ready",
        "seal_allowed": True,
        "seal_hash": "b" * 64,
        "next_action": "build_operator_handoff_runbook",
        "reasons": ["final_end_state_certified", "final_seal_prepared"],
    }
    payload.update(overrides)
    record = FinalSealStampRecord(**payload)
    FinalSealStampJsonlStore(profile / FINAL_SEAL_STAMP_FILENAME).append(record)
    return record


def test_operator_handoff_runbook_ready_happy_path(tmp_path) -> None:
    profile = tmp_path / "profile"
    seal = _write_seal(profile)

    payload = build_operator_handoff_runbook(profile)
    record = payload["runbook_record"]

    assert record["handoff_status"] == "ready"
    assert record["handoff_decision"] == "operator_handoff_ready"
    assert record["handoff_allowed"] is True
    assert record["source_seal_id"] == seal.seal_id
    assert record["source_seal_hash"] == seal.seal_hash
    assert record["source_end_state"] == "READY_AFTER_OPERATOR_ACCEPTANCE"
    assert record["next_action"] == "operator_runtime_ready"
    assert record["required_operator_checks"] == [
        "confirm_profile_path",
        "confirm_final_seal_hash",
        "confirm_registry_unchanged",
        "confirm_no_pending_blockers",
    ]
    assert len(record["runbook_hash"]) == 64


def test_operator_handoff_runbook_blocks_missing_seal(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = build_operator_handoff_runbook(profile)["runbook_record"]

    assert record["handoff_allowed"] is False
    assert record["handoff_decision"] == "operator_handoff_blocked"
    assert "final_seal_stamp_missing" in record["reasons"]
    assert record["next_action"] == "build_final_seal_stamp"


def test_operator_handoff_runbook_blocks_unready_seal(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_seal(profile, seal_status="blocked", seal_decision="final_seal_blocked")

    record = build_operator_handoff_runbook(profile)["runbook_record"]

    assert record["handoff_allowed"] is False
    assert "seal_status_not_ready" in record["reasons"]
    assert "seal_decision_not_ready" in record["reasons"]


def test_operator_handoff_runbook_blocks_registry_change(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_seal(profile, registry_change_applied=True)

    record = build_operator_handoff_runbook(profile)["runbook_record"]

    assert record["handoff_allowed"] is False
    assert "registry_changed_after_seal" in record["reasons"]


def test_operator_handoff_runbook_blocks_next_action_mismatch(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_seal(profile, next_action="build_final_end_state_certificate")

    record = build_operator_handoff_runbook(profile)["runbook_record"]

    assert record["handoff_allowed"] is False
    assert "seal_next_action_not_operator_handoff" in record["reasons"]


def test_operator_handoff_runbook_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_seal(profile)
    build_operator_handoff_runbook(profile)

    summary = summarize_operator_handoff_runbooks(
        profile / OPERATOR_HANDOFF_RUNBOOK_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "operator_handoff_runbook"
    assert summary["total_runbook_count"] == 1
    assert summary["latest_handoff_allowed"] is True
    assert summary["latest_handoff_decision"] == "operator_handoff_ready"
    assert summary["latest_handoff_status"] == "ready"
    assert summary["latest_next_action"] == "operator_runtime_ready"
