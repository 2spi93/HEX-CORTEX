from hex_cortex.memory.cortex_trust import compute_trusted_plan


def test_trusted_plan_allows_high_confidence_known_plan() -> None:
    payload = compute_trusted_plan(
        operator_intent_known=True,
        plan_known=True,
        preference_match=1.0,
        stability_score=1.0,
        registered_unit_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["trusted_plan"] is True
    assert payload["score"] == 100.0
    assert payload["next_action"] == "allow_auto_safe_operator_units"
    assert payload["blockers"] == []


def test_trusted_plan_blocks_unknown_intent_even_with_good_score() -> None:
    payload = compute_trusted_plan(
        operator_intent_known=False,
        plan_known=True,
        preference_match=1.0,
        stability_score=1.0,
        registered_unit_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["trusted_plan"] is False
    assert "operator_intent_unknown" in payload["blockers"]


def test_trusted_plan_blocks_low_score() -> None:
    payload = compute_trusted_plan(
        operator_intent_known=True,
        plan_known=True,
        preference_match=0.5,
        stability_score=0.5,
        registered_unit_rate=0.5,
        receipt_rate=0.5,
    )

    assert payload["trusted_plan"] is False
    assert "trust_score_below_threshold" in payload["blockers"]


def test_trusted_plan_blocks_out_of_range() -> None:
    payload = compute_trusted_plan(
        operator_intent_known=True,
        plan_known=True,
        preference_match=1.2,
        stability_score=1.0,
        registered_unit_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["trusted_plan"] is False
    assert "preference_match_out_of_range" in payload["blockers"]
