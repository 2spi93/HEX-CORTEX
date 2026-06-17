from hex_cortex.memory.profile_operator_cycle import run_profile_operator_cycle


def test_profile_cycle_trace_payload(tmp_path) -> None:
    payload = run_profile_operator_cycle(tmp_path / "profile")

    assert payload["cycle_trace_count"] == 1
    assert payload["cycle_trace_path"].endswith("profile-cycle.jsonl")
