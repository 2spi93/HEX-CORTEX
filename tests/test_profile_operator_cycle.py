from hex_cortex.memory.profile_operator_cycle import run_profile_operator_cycle


def test_profile_operator_cycle_returns_plan_when_dispatch_skipped(tmp_path) -> None:
    payload = run_profile_operator_cycle(tmp_path / "profile")

    assert payload["cycle_type"] == "profile_operator_cycle"
    assert payload["dispatch_status"] == "skipped"
    assert payload["cycle_status"] == "plan_required"
    assert payload["plan_action"] == "repair_profile_readiness"
