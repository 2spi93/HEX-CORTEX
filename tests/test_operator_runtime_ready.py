from hex_cortex.memory.operator_handoff_runbook import (
    OPERATOR_HANDOFF_RUNBOOK_FILENAME,
    OperatorHandoffRunbookJsonlStore,
    OperatorHandoffRunbookRecord,
)
from hex_cortex.memory.operator_runtime_ready import (
    OPERATOR_RUNTIME_READY_FILENAME,
    build_operator_runtime_ready,
    summarize_operator_runtime_ready,
)


def _write_runbook(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "selected_skill": "operator_watch_review",
        "source_seal_id": "final_seal_1",
        "source_seal_hash": "a" * 64,
        "source_seal_decision": "final_seal_ready",
        "source_end_state": "READY_AFTER_OPERATOR_ACCEPTANCE",
        "handoff_status": "ready",
        "handoff_decision": "operator_handoff_ready",
        "handoff_allowed": True,
        "runbook_hash": "b" * 64,
        "next_action": "operator_runtime_ready",
        "required_operator_checks": [
            "confirm_profile_path",
            "confirm_final_seal_hash",
            "confirm_registry_unchanged",
            "confirm_no_pending_blockers",
        ],
        "reasons": ["final_seal_ready", "operator_handoff_prepared"],
    }
    payload.update(overrides)
    record = OperatorHandoffRunbookRecord(**payload)
    OperatorHandoffRunbookJsonlStore(
        profile / OPERATOR_HANDOFF_RUNBOOK_FILENAME
    ).append(record)
    return record


def test_operator_runtime_ready_happy_path(tmp_path) -> None:
    profile = tmp_path / "profile"
    runbook = _write_runbook(profile)

    payload = build_operator_runtime_ready(profile)
    record = payload["ready_record"]

    assert record["runtime_status"] == "ready"
    assert record["runtime_decision"] == "operator_runtime_ready"
    assert record["runtime_allowed"] is True
    assert record["next_action"] == "await_operator_command"
    assert record["source_runbook_id"] == runbook.runbook_id
    assert record["source_runbook_hash"] == runbook.runbook_hash
    assert len(record["runtime_hash"]) == 64


def test_operator_runtime_ready_blocks_missing_runbook(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = build_operator_runtime_ready(profile)["ready_record"]

    assert record["runtime_allowed"] is False
    assert record["runtime_decision"] == "operator_runtime_blocked"
    assert "operator_handoff_runbook_missing" in record["reasons"]
    assert record["next_action"] == "build_operator_handoff_runbook"


def test_operator_runtime_ready_blocks_unready_handoff(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_runbook(profile, handoff_status="blocked")

    record = build_operator_runtime_ready(profile)["ready_record"]

    assert record["runtime_allowed"] is False
    assert "handoff_status_not_ready" in record["reasons"]


def test_operator_runtime_ready_blocks_next_action_mismatch(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_runbook(profile, next_action="await_operator_command")

    record = build_operator_runtime_ready(profile)["ready_record"]

    assert record["runtime_allowed"] is False
    assert "handoff_next_action_not_runtime_ready" in record["reasons"]


def test_operator_runtime_ready_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_runbook(profile)
    build_operator_runtime_ready(profile)

    summary = summarize_operator_runtime_ready(profile / OPERATOR_RUNTIME_READY_FILENAME)

    assert summary["exists"] is True
    assert summary["inspect_type"] == "operator_runtime_ready"
    assert summary["total_ready_count"] == 1
    assert summary["latest_runtime_allowed"] is True
    assert summary["latest_runtime_decision"] == "operator_runtime_ready"
    assert summary["latest_runtime_status"] == "ready"
    assert summary["latest_next_action"] == "await_operator_command"
