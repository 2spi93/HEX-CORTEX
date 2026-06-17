from hex_cortex.memory.invariant_scanner import scan_profile_invariants


def test_invariant_scanner_allows_empty_profile(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = scan_profile_invariants(profile)
    record = payload["scan_record"]

    assert record["invariant_decision"] == "invariants_ok"
    assert record["violation_count"] == 0
    assert record["next_action"] == "continue"
