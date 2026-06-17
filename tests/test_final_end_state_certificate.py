from hex_cortex.memory.final_end_state_certificate import (
    FINAL_END_STATE_CERTIFICATE_FILENAME,
    build_final_end_state_certificate,
    summarize_final_end_state_certificates,
)
from hex_cortex.memory.profile_panel_snapshot import (
    PROFILE_PANEL_SNAPSHOT_FILENAME,
    ProfilePanelSnapshotJsonlStore,
    ProfilePanelSnapshotRecord,
)
from hex_cortex.memory.profile_resync_gate import (
    PROFILE_RESYNC_GATE_FILENAME,
    ProfileResyncGateJsonlStore,
    ProfileResyncGateRecord,
)


def _write_ready_sources(profile):
    gate = _write_gate(profile)
    panel = _write_panel(profile)
    return gate, panel


def _write_gate(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "selected_skill": "operator_watch_review",
        "source_resync_id": "profile_resync_ready_1",
        "resync_decision": "resync_ready",
        "gate_status": "ready",
        "gate_decision": "gate_ready",
        "gate_allowed": True,
        "next_action": "prepare_freeze_stamp",
        "gate_hash": "a" * 64,
        "reasons": ["ready"],
    }
    payload.update(overrides)
    record = ProfileResyncGateRecord(**payload)
    ProfileResyncGateJsonlStore(profile / PROFILE_RESYNC_GATE_FILENAME).append(record)
    return record


def _write_panel(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "selected_skill": "operator_watch_review",
        "display_state": "ready",
        "safe_to_continue": True,
        "next_action": "prepare_freeze_stamp",
        "pack_decision": "pack_watch",
        "construction_decision": "construction_watch",
        "freeze_decision": "freeze_watch",
        "manual_choice": "accept",
        "resync_decision": "resync_ready",
        "gate_decision": "gate_ready",
        "invariant_decision": "invariants_ok",
        "violation_count": 0,
    }
    payload.update(overrides)
    record = ProfilePanelSnapshotRecord(**payload)
    ProfilePanelSnapshotJsonlStore(profile / PROFILE_PANEL_SNAPSHOT_FILENAME).append(record)
    return record


def test_final_end_state_certificate_ready_happy_path(tmp_path) -> None:
    profile = tmp_path / "profile"
    gate, panel = _write_ready_sources(profile)

    payload = build_final_end_state_certificate(profile)
    record = payload["certificate_record"]

    assert record["end_state"] == "READY_AFTER_OPERATOR_ACCEPTANCE"
    assert record["certificate_status"] == "certified"
    assert record["certificate_decision"] == "final_end_state_certified"
    assert record["certificate_allowed"] is True
    assert record["safe_to_continue"] is True
    assert record["registry_change_applied"] is False
    assert record["next_action"] == "prepare_freeze_stamp"
    assert record["source_gate_id"] == gate.gate_id
    assert record["source_gate_hash"] == gate.gate_hash
    assert record["source_panel_id"] == panel.panel_id
    assert record["blocker_count"] == 0
    assert record["active_blockers"] == []
    assert len(record["certificate_hash"]) == 64


def test_final_end_state_certificate_blocks_when_gate_not_ready(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_gate(profile, gate_decision="gate_watch")
    _write_panel(profile)

    record = build_final_end_state_certificate(profile)["certificate_record"]

    assert record["certificate_allowed"] is False
    assert record["certificate_status"] == "blocked"
    assert "gate_decision_not_ready" in record["active_blockers"]


def test_final_end_state_certificate_blocks_when_panel_not_safe(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_gate(profile)
    _write_panel(profile, safe_to_continue=False)

    record = build_final_end_state_certificate(profile)["certificate_record"]

    assert record["certificate_allowed"] is False
    assert "panel_not_safe_to_continue" in record["active_blockers"]


def test_final_end_state_certificate_blocks_when_manual_choice_not_accept(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_gate(profile)
    _write_panel(profile, manual_choice="reject")

    record = build_final_end_state_certificate(profile)["certificate_record"]

    assert record["certificate_allowed"] is False
    assert "manual_choice_not_accept" in record["active_blockers"]


def test_final_end_state_certificate_blocks_when_violation_count_nonzero(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_gate(profile)
    _write_panel(profile, violation_count=1)

    record = build_final_end_state_certificate(profile)["certificate_record"]

    assert record["certificate_allowed"] is False
    assert "panel_violations_present" in record["active_blockers"]


def test_final_end_state_certificate_blocks_when_next_action_mismatch(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_gate(profile)
    _write_panel(profile, next_action="rerun_construction_status")

    record = build_final_end_state_certificate(profile)["certificate_record"]

    assert record["certificate_allowed"] is False
    assert "next_action_not_prepare_freeze_stamp" in record["active_blockers"]


def test_final_end_state_certificate_registry_change_applied_false(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_ready_sources(profile)

    record = build_final_end_state_certificate(profile)["certificate_record"]

    assert record["registry_change_applied"] is False
    assert "registry_unchanged" in record["reasons"]


def test_final_end_state_certificate_hash_is_stable(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_ready_sources(profile)

    first = build_final_end_state_certificate(profile)["certificate_record"]
    second = build_final_end_state_certificate(profile)["certificate_record"]

    assert first["certificate_id"] != second["certificate_id"]
    assert first["created_at"] != second["created_at"]
    assert first["certificate_hash"] == second["certificate_hash"]


def test_final_end_state_certificate_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_ready_sources(profile)
    build_final_end_state_certificate(profile)

    summary = summarize_final_end_state_certificates(
        profile / FINAL_END_STATE_CERTIFICATE_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "final_end_state_certificate"
    assert summary["total_certificate_count"] == 1
    assert summary["latest_end_state"] == "READY_AFTER_OPERATOR_ACCEPTANCE"
    assert summary["latest_certificate_allowed"] is True
    assert summary["latest_certificate_decision"] == "final_end_state_certified"
    assert summary["latest_certificate_status"] == "certified"
    assert summary["latest_safe_to_continue"] is True
    assert summary["latest_registry_change_applied"] is False
    assert summary["latest_next_action"] == "prepare_freeze_stamp"
    assert summary["latest_selected_skill"] == "operator_watch_review"
