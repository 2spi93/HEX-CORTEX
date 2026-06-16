from hex_cortex.memory.profile_dispatch_safety import inspect_profile_dispatch_safety


def test_profile_dispatch_safety_allows_ready_run_action(tmp_path) -> None:
    payload = inspect_profile_dispatch_safety(
        tmp_path / "profile",
        {
            "status": "ready",
            "decision": "allow",
            "next_action": "run_cortex_pipeline",
            "latest_snapshot_id": "readiness_a",
        },
    )

    assert payload["allowed"] is True
    assert payload["safety_status"] == "allow"
    assert payload["safety_reasons"] == []


def test_profile_dispatch_safety_blocks_watch_action(tmp_path) -> None:
    payload = inspect_profile_dispatch_safety(
        tmp_path / "profile",
        {
            "status": "watch",
            "decision": "watch",
            "next_action": "review_profile_watch_reasons",
            "latest_snapshot_id": "readiness_a",
        },
    )

    assert payload["allowed"] is False
    assert payload["safety_status"] == "block"
    assert "operator_decision_not_allow" in payload["safety_reasons"]
