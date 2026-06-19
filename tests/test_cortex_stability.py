from hex_cortex.memory.cortex_stability import compute_cortex_stability


def test_stability_stable_when_signals_are_good() -> None:
    payload = compute_cortex_stability(
        success_rate=1.0,
        error_rate=0.0,
        unknown_unit_rate=0.0,
        citation_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["stability_allowed"] is True
    assert payload["stability_status"] == "stable"
    assert payload["score"] == 100.0
    assert payload["repair_suggestions"] == []


def test_stability_rebalances_when_quality_drops() -> None:
    payload = compute_cortex_stability(
        success_rate=0.7,
        error_rate=0.2,
        unknown_unit_rate=0.3,
        citation_rate=0.5,
        receipt_rate=0.7,
    )

    assert payload["stability_allowed"] is True
    assert payload["stability_status"] == "rebalance"
    assert "add_failure_fixture" in payload["repair_suggestions"]
    assert "register_or_reject_unknown_units" in payload["repair_suggestions"]
    assert "increase_source_citation_coverage" in payload["repair_suggestions"]
    assert "increase_receipt_coverage" in payload["repair_suggestions"]


def test_stability_blocks_out_of_range_inputs() -> None:
    payload = compute_cortex_stability(
        success_rate=1.2,
        error_rate=0.0,
        unknown_unit_rate=0.0,
        citation_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["stability_allowed"] is False
    assert "success_rate_out_of_range" in payload["blockers"]
