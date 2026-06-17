from hex_cortex.memory.profile_resync_gate import (
    build_profile_resync_gate,
    summarize_profile_resync_gates,
)


def test_profile_resync_gate_blocks_missing_resync(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_profile_resync_gate(profile)
    summary = summarize_profile_resync_gates(profile / "profile-resync-gate.jsonl")
    record = payload["gate_record"]

    assert record["gate_decision"] == "gate_blocked"
    assert record["gate_allowed"] is False
    assert len(record["gate_hash"]) == 64
    assert summary["latest_gate_decision"] == "gate_blocked"
