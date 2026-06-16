from hex_cortex.memory.profile_next_action import inspect_profile_next_action


def test_profile_next_action_repairs_missing_profile(tmp_path) -> None:
    payload = inspect_profile_next_action(tmp_path / "profile")

    assert payload["action_type"] == "profile_next_action"
    assert payload["decision"] == "block"
    assert payload["next_action"] == "repair_profile_readiness"
