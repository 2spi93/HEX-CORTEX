from hex_cortex.memory.profile_next_action_dispatch import dispatch_profile_next_action


def test_profile_dispatch_skips_empty_profile(tmp_path) -> None:
    payload = dispatch_profile_next_action(tmp_path / "profile")

    assert payload["dispatch_status"] == "skipped"
    assert payload["pipeline_result"] is None
