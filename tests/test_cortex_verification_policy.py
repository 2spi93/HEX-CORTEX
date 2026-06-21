import pytest

from hex_cortex.memory.cortex_self_consistency import aggregate_self_consistency
from hex_cortex.memory.cortex_verification_policy import decide_verification_action


def test_accept_when_verified_and_confident() -> None:
    receipt = aggregate_self_consistency(["42"] * 20)
    decision = decide_verification_action(receipt, target_confidence=0.7)
    assert decision["action"] == "accept"
    assert decision["fail_closed"] is False
    assert decision["confidence_gap"] == 0.0


def test_resample_when_more_samples_can_reach_target() -> None:
    # 5 unanimous samples: agreement 1.0 but Wilson lower ~0.69 < 0.70.
    receipt = aggregate_self_consistency(["42"] * 5)
    assert receipt["status"] == "verified"
    assert receipt["confidence_wilson_lower"] < 0.7
    decision = decide_verification_action(receipt, target_confidence=0.7, max_samples=16)
    assert decision["action"] == "resample"
    assert decision["recommended_total_samples"] > 5
    assert decision["recommended_additional_samples"] >= 1


def test_escalate_when_agreement_too_low_to_ever_reach_target() -> None:
    # Agreement 0.6 <= target 0.7: no amount of resampling can reach it.
    receipt = aggregate_self_consistency(["a", "a", "a", "b", "b"])
    assert receipt["agreement_ratio"] == 0.6
    decision = decide_verification_action(
        receipt,
        target_confidence=0.7,
        stronger_brain_available=True,
    )
    assert decision["action"] == "escalate"
    assert decision["reason"] == "resampling_cannot_reach_target_escalate"
    assert decision["fail_closed"] is True


def test_refuse_when_no_escalation_path() -> None:
    receipt = aggregate_self_consistency(["a", "a", "a", "b", "b"])
    decision = decide_verification_action(
        receipt,
        target_confidence=0.7,
        stronger_brain_available=False,
    )
    assert decision["action"] == "refuse"
    assert decision["fail_closed"] is True


def test_escalate_when_sample_budget_exhausted() -> None:
    # Agreement just above target but the cap is too small to ever reach it.
    receipt = aggregate_self_consistency(["x"] * 5)  # agreement 1.0
    decision = decide_verification_action(
        receipt,
        target_confidence=0.7,
        max_samples=3,
        stronger_brain_available=True,
    )
    # 5 samples already used, cap 3 -> cannot resample further; escalate.
    assert decision["action"] == "escalate"
    assert decision["reason"] == "sample_budget_exhausted_escalate"


def test_invalid_inputs_rejected() -> None:
    receipt = aggregate_self_consistency(["x"] * 3)
    with pytest.raises(ValueError):
        decide_verification_action({}, target_confidence=0.7)
    with pytest.raises(ValueError):
        decide_verification_action(receipt, target_confidence=1.5)
    with pytest.raises(ValueError):
        decide_verification_action(receipt, max_samples=0)
