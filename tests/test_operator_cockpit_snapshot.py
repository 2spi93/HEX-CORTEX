import json

from hex_cortex.memory.operator_cockpit_snapshot import (
    OPERATOR_COCKPIT_SNAPSHOT_FILENAME,
    build_operator_cockpit_snapshot,
    summarize_operator_cockpit_snapshots,
)


def _append(profile, filename, payload):
    path = profile / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _ready_profile(profile):
    _append(profile, "final-end-state-certificate.jsonl", {
        "profile_path": str(profile), "selected_skill": "operator_watch_review",
        "source_gate_id": "gate", "source_gate_hash": "a" * 64,
        "source_panel_id": "panel", "source_resync_decision": "resync_ready",
        "source_gate_decision": "gate_ready", "source_panel_display_state": "ready",
        "manual_choice": "accept", "safe_to_continue": True,
        "registry_change_applied": False, "next_action": "prepare_freeze_stamp",
        "end_state": "READY_AFTER_OPERATOR_ACCEPTANCE",
        "certificate_status": "certified", "certificate_decision": "final_end_state_certified",
        "certificate_allowed": True, "blocker_count": 0, "active_blockers": [],
        "reasons": ["registry_unchanged"], "certificate_hash": "b" * 64,
    })
    _append(profile, "final-freeze-stamp.jsonl", {
        "profile_path": str(profile), "selected_skill": "operator_watch_review",
        "source_certificate_id": "cert", "source_certificate_hash": "b" * 64,
        "source_end_state": "READY_AFTER_OPERATOR_ACCEPTANCE", "safe_to_continue": True,
        "registry_change_applied": False, "stamp_status": "ready",
        "stamp_decision": "final_stamp_ready", "stamp_allowed": True,
        "stamp_hash": "c" * 64, "next_action": "build_operator_handoff_runbook",
        "reasons": ["stamp_prepared"],
    })
    _append(profile, "final-seal-stamp.jsonl", {
        "profile_path": str(profile), "selected_skill": "operator_watch_review",
        "source_certificate_id": "cert", "source_certificate_hash": "b" * 64,
        "source_end_state": "READY_AFTER_OPERATOR_ACCEPTANCE", "safe_to_continue": True,
        "registry_change_applied": False, "seal_status": "ready",
        "seal_decision": "final_seal_ready", "seal_allowed": True,
        "seal_hash": "d" * 64, "next_action": "build_operator_handoff_runbook",
        "reasons": ["final_seal_prepared"],
    })
    _append(profile, "operator-handoff-runbook.jsonl", {
        "profile_path": str(profile), "selected_skill": "operator_watch_review",
        "source_seal_id": "seal", "source_seal_hash": "d" * 64,
        "source_seal_decision": "final_seal_ready",
        "source_end_state": "READY_AFTER_OPERATOR_ACCEPTANCE",
        "handoff_status": "ready", "handoff_decision": "operator_handoff_ready",
        "handoff_allowed": True, "runbook_hash": "e" * 64,
        "next_action": "operator_runtime_ready",
        "required_operator_checks": ["confirm_profile_path"],
        "reasons": ["operator_handoff_prepared"],
    })
    _append(profile, "operator-runtime-ready.jsonl", {
        "profile_path": str(profile), "selected_skill": "operator_watch_review",
        "source_runbook_id": "runbook", "source_runbook_hash": "e" * 64,
        "runtime_status": "ready", "runtime_decision": "operator_runtime_ready",
        "runtime_allowed": True, "runtime_hash": "f" * 64,
        "next_action": "await_operator_command",
        "reasons": ["runtime_marker_prepared"],
    })


def test_operator_cockpit_snapshot_ready_happy_path(tmp_path) -> None:
    profile = tmp_path / "profile"
    _ready_profile(profile)
    record = build_operator_cockpit_snapshot(profile)["cockpit_record"]
    assert record["cockpit_allowed"] is True
    assert record["cockpit_decision"] == "operator_cockpit_ready"
    assert record["cockpit_mode"] == "command"
    assert record["next_action"] == "await_operator_command"
    assert record["active_blockers"] == []
    assert len(record["source_hashes"]) == 5
    assert len(record["cockpit_hash"]) == 64


def test_operator_cockpit_snapshot_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _ready_profile(profile)
    build_operator_cockpit_snapshot(profile)
    summary = summarize_operator_cockpit_snapshots(profile / OPERATOR_COCKPIT_SNAPSHOT_FILENAME)
    assert summary["exists"] is True
    assert summary["latest_cockpit_allowed"] is True
    assert summary["latest_cockpit_status"] == "ready"
    assert summary["latest_next_action"] == "await_operator_command"


def test_operator_cockpit_snapshot_blocks_empty_profile(tmp_path) -> None:
    record = build_operator_cockpit_snapshot(tmp_path / "profile")["cockpit_record"]
    assert record["cockpit_allowed"] is False
    assert "runtime_not_ready" in record["active_blockers"]
