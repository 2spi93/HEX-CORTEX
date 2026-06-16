from hex_cortex.memory.profile_operator_control import run_profile_operator_control


def test_profile_operator_command_missing_profile(tmp_path) -> None:
    payload = run_profile_operator_control(tmp_path / "profile")

    assert payload["status"] == "blocked"
    assert payload["decision"] == "block"
