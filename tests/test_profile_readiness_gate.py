from hex_cortex.memory.profile_readiness_gate import inspect_profile_readiness_gate


def test_profile_readiness_gate_blocks_when_snapshot_missing(tmp_path) -> None:
    payload = inspect_profile_readiness_gate(tmp_path / "profile")

    assert payload["decision"] == "block"
    assert payload["reason"] == "readiness_snapshot_missing"
    assert payload["snapshot_exists"] is False
