import json

from hex_cortex.memory.operator_command_intake import (
    OPERATOR_COMMAND_INTAKE_FILENAME,
    ingest_operator_command,
    summarize_operator_command_intakes,
)


def _ready_cockpit(profile):
    path = profile / "operator-cockpit-snapshot.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "profile_path": str(profile),
        "selected_skill": "operator_watch_review",
        "cockpit_status": "ready",
        "cockpit_decision": "operator_cockpit_ready",
        "cockpit_allowed": True,
        "cockpit_mode": "command",
        "next_action": "await_operator_command",
        "blocker_count": 0,
        "active_blockers": [],
        "source_hashes": ["a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64],
        "cockpit_hash": "f" * 64,
        "reasons": ["all_operator_surfaces_ready"],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def test_operator_command_intake_accepts_inspect_when_cockpit_ready(tmp_path) -> None:
    profile = tmp_path / "profile"
    _ready_cockpit(profile)

    record = ingest_operator_command(profile, "inspect status")["intake_record"]

    assert record["command_kind"] == "inspect"
    assert record["command_allowed"] is True
    assert record["command_decision"] == "operator_command_accepted"
    assert record["command_route"] == "route_inspect"
    assert record["next_action"] == "route_inspect"
    assert len(record["command_hash"]) == 64


def test_operator_command_intake_blocks_execute_even_when_cockpit_ready(tmp_path) -> None:
    profile = tmp_path / "profile"
    _ready_cockpit(profile)

    record = ingest_operator_command(profile, "execute live order")["intake_record"]

    assert record["command_kind"] == "execute"
    assert record["command_allowed"] is False
    assert "execute_requires_separate_gate" in record["blockers"]
    assert record["next_action"] == "build_execution_authorization_gate"


def test_operator_command_intake_blocks_when_cockpit_missing(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = ingest_operator_command(profile, "inspect status")["intake_record"]

    assert record["command_allowed"] is False
    assert "cockpit_not_ready" in record["blockers"]
    assert record["next_action"] == "build_operator_cockpit_snapshot"


def test_operator_command_intake_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _ready_cockpit(profile)
    ingest_operator_command(profile, "simulate next step")

    summary = summarize_operator_command_intakes(profile / OPERATOR_COMMAND_INTAKE_FILENAME)

    assert summary["exists"] is True
    assert summary["inspect_type"] == "operator_command_intake"
    assert summary["total_intake_count"] == 1
    assert summary["latest_command_kind"] == "simulate"
    assert summary["latest_command_allowed"] is True
    assert summary["latest_command_route"] == "route_simulate"
