from hex_cortex.memory.profile_panel_snapshot import build_profile_panel_snapshot


def test_profile_panel_snapshot_outputs_compact_state(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_profile_panel_snapshot(profile)
    record = payload["panel_record"]

    assert payload["panel_count"] == 1
    assert record["display_state"] in {"ready", "watch", "blocked"}
    assert "safe_to_continue" in record
