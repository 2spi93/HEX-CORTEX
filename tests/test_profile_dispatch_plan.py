from hex_cortex.memory.profile_dispatch_recovery import inspect_profile_dispatch_recovery


def test_profile_dispatch_plan_returns_repair_for_empty_profile(tmp_path) -> None:
    payload = inspect_profile_dispatch_recovery(tmp_path / "profile")

    assert payload["recovery_type"] == "profile_dispatch_recovery"
    assert payload["recovery_action"] == "repair_profile_readiness"
    assert "hexctl" in payload["recommended_command"]
