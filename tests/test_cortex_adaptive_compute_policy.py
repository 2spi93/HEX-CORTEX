import pytest

from hex_cortex.memory.cortex_adaptive_compute_policy import select_compute_strategy


def test_high_confidence_uses_single_cheap_call() -> None:
    s = select_compute_strategy(difficulty="low", risk="low", prior_confidence=0.9)
    assert s["strategy"] == "small_single"
    assert s["samples"] == 1
    assert s["expected_model_calls"] == 1
    assert s["use_self_consistency"] is False


def test_medium_confidence_uses_weighted_self_consistency() -> None:
    s = select_compute_strategy(difficulty="medium", risk="low", prior_confidence=0.6)
    assert s["strategy"] == "small_self_consistency"
    assert s["weighted_vote"] is True
    assert s["samples"] == 3


def test_low_confidence_pulls_in_external_verification() -> None:
    s = select_compute_strategy(difficulty="high", risk="low", prior_confidence=0.2)
    assert s["strategy"] == "small_tool_second_model_critique"
    assert s["use_adversarial_critique"] is True
    assert s["escalate_to_second_model"] is True


def test_high_risk_escalates_to_large_with_human_signoff() -> None:
    s = select_compute_strategy(difficulty="medium", risk="high")
    assert s["strategy"] == "large_model_reinforced_human"
    assert s["requested_tier"] == "large"
    assert s["require_human_validation"] is True
    assert s["reinforced_tests"] is True


def test_high_risk_without_large_model_escalates_second_model() -> None:
    s = select_compute_strategy(difficulty="medium", risk="high", large_model_available=False)
    assert s["requested_tier"] == "small"
    assert s["escalate_to_second_model"] is True


def test_exact_arithmetic_always_uses_deterministic_tool() -> None:
    s = select_compute_strategy(
        difficulty="low", risk="low", domain="arithmetic_reasoning", prior_confidence=0.95
    )
    # Even at high confidence, mental arithmetic is never trusted.
    assert s["use_deterministic_tool"] is True


def test_difficulty_drives_strategy_when_no_prior_confidence() -> None:
    easy = select_compute_strategy(difficulty="low", risk="low")
    hard = select_compute_strategy(difficulty="critical", risk="low")
    assert easy["strategy"] == "small_single"
    assert hard["strategy"] == "small_tool_second_model_critique"


def test_invalid_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        select_compute_strategy(difficulty="bogus", risk="low")
    with pytest.raises(ValueError):
        select_compute_strategy(difficulty="low", risk="nope")
    with pytest.raises(ValueError):
        select_compute_strategy(difficulty="low", risk="low", prior_confidence=2.0)
