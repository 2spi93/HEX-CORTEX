"""Escalation policy over a self-consistency consensus receipt.

This is the orchestration brain that closes the loop between the risk-aware
router and the verification layer. Given the consensus a brain produced, it
decides — purely, with no model call — what to do next:

    accept    consensus is verified and confident enough
    resample  more samples from the same brain can still reach the target
    escalate  resampling cannot reach the target; route to a stronger brain
    refuse    nothing left to try; fail closed rather than guess

The key optimization: the lower bound of the Wilson interval asymptotes to the
observed agreement as samples grow. So if the observed agreement is already at
or below the target confidence, *no amount of resampling can ever reach it* —
the policy escalates immediately instead of burning samples. When resampling
can help, it computes the minimum additional samples needed.
"""

from __future__ import annotations

from hex_cortex.memory.cortex_self_consistency import _wilson_lower

_ACTIONS = {"accept", "resample", "escalate", "refuse"}


def decide_verification_action(
    consensus_receipt: dict[str, object],
    *,
    target_confidence: float = 0.7,
    max_samples: int = 16,
    stronger_brain_available: bool = False,
) -> dict[str, object]:
    """Map a consensus receipt to the next verification action.

    ``consensus_receipt`` is the dict returned by ``aggregate_self_consistency``.
    """
    for key in ("status", "agreement_ratio", "confidence_wilson_lower", "sample_count"):
        if key not in consensus_receipt:
            raise ValueError(f"consensus_receipt missing field: {key}")
    if not 0.0 <= target_confidence <= 1.0:
        raise ValueError("target_confidence out of range")
    if max_samples < 1:
        raise ValueError("max_samples must be >= 1")

    status = str(consensus_receipt["status"])
    agreement = float(consensus_receipt["agreement_ratio"])
    confidence = float(consensus_receipt["confidence_wilson_lower"])
    samples_used = int(consensus_receipt["sample_count"])

    if status == "verified" and confidence >= target_confidence:
        return _decision(
            "accept",
            "consensus_verified_and_confident",
            target_confidence,
            confidence,
            samples_used,
        )

    # Can resampling the same brain ever reach the target? Only if the observed
    # agreement strictly exceeds it (Wilson lower bound -> agreement as n -> inf).
    reachable = agreement > target_confidence
    needed = _min_samples_for_target(agreement, target_confidence, max_samples) if reachable else None
    if reachable and needed is not None and needed > samples_used:
        decision = _decision(
            "resample",
            "more_samples_can_reach_target",
            target_confidence,
            confidence,
            samples_used,
        )
        decision["recommended_total_samples"] = needed
        decision["recommended_additional_samples"] = needed - samples_used
        return decision

    if stronger_brain_available:
        reason = (
            "sample_budget_exhausted_escalate"
            if reachable
            else "resampling_cannot_reach_target_escalate"
        )
        return _decision("escalate", reason, target_confidence, confidence, samples_used)

    return _decision(
        "refuse",
        "no_confident_consensus_and_no_escalation_path",
        target_confidence,
        confidence,
        samples_used,
    )


def _min_samples_for_target(
    agreement: float,
    target_confidence: float,
    cap: int,
) -> int | None:
    """Smallest n at which the Wilson lower bound for ``agreement`` >= target.

    Returns None when the target is unreachable by resampling at this agreement
    (i.e. the agreement itself is at or below the target confidence).
    """
    if agreement <= target_confidence:
        return None
    for n in range(1, cap + 1):
        if _wilson_lower(agreement, float(n)) >= target_confidence:
            return n
    return None


def _decision(
    action: str,
    reason: str,
    target_confidence: float,
    confidence: float,
    samples_used: int,
) -> dict[str, object]:
    assert action in _ACTIONS
    return {
        "policy_type": "cortex_verification_policy_v1",
        "action": action,
        "reason": reason,
        "target_confidence": target_confidence,
        "achieved_confidence": confidence,
        "confidence_gap": round(max(0.0, target_confidence - confidence), 6),
        "samples_used": samples_used,
        "model_call_performed": False,
        "fail_closed": action in {"escalate", "refuse"},
    }
