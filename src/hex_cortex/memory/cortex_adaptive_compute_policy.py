"""Adaptive compute policy — route to a strategy, not just a model.

Test-time compute should be allocated by real difficulty, not spent uniformly.
Given a task's difficulty/risk (and optionally the confidence of a first cheap
pass) this picks a full cognitive *strategy*:

    small_single                      high confidence -> one cheap answer
    small_self_consistency            medium -> a few samples + weighted vote
    small_tool_second_model_critique  low -> deterministic tool + 2nd model + adversarial critique
    large_model_reinforced_human      high risk -> big model + reinforced tests + human sign-off

Two rules from the operator's plan are baked in: self-consistency multiplies
calls so it is conditional, never automatic; and on exact-arithmetic domains the
LLM's mental arithmetic is never trusted — a deterministic Python tool computes
the result (Program-of-Thoughts). Pure and cold: it emits a plan, runs nothing.
The chosen ``requested_tier`` is what a runtime then feeds to the GPU governor.
"""

from __future__ import annotations

_POLICY_TYPE = "cortex_adaptive_compute_strategy_v1"
_LEVELS = {"low", "medium", "high", "critical"}
_EXACT_DOMAINS = {"arithmetic_reasoning", "arithmetic", "math", "exact_numeric"}
# Pseudo-confidence used only when no measured prior_confidence is supplied.
_DIFFICULTY_CONFIDENCE = {"low": 0.85, "medium": 0.65, "high": 0.45, "critical": 0.30}


def select_compute_strategy(
    *,
    difficulty: str,
    risk: str,
    domain: str | None = None,
    prior_confidence: float | None = None,
    python_available: bool = True,
    large_model_available: bool = True,
    target_confidence: float = 0.7,
) -> dict[str, object]:
    """Choose a cognitive strategy proportionate to difficulty and risk."""
    if difficulty not in _LEVELS:
        raise ValueError("difficulty must be low/medium/high/critical")
    if risk not in _LEVELS:
        raise ValueError("risk must be low/medium/high/critical")
    if prior_confidence is not None and not 0.0 <= prior_confidence <= 1.0:
        raise ValueError("prior_confidence out of range")
    if not 0.0 <= target_confidence <= 1.0:
        raise ValueError("target_confidence out of range")

    exact = (domain or "").strip().lower() in _EXACT_DOMAINS
    use_python = exact and python_available

    # High risk dominates: capability + independent verification + human gate.
    if risk in {"high", "critical"}:
        tier = "large" if large_model_available else "small"
        return _strategy(
            "large_model_reinforced_human",
            requested_tier=tier,
            samples=3,
            weighted_vote=True,
            use_self_consistency=True,
            use_deterministic_tool=use_python,
            use_adversarial_critique=True,
            escalate_to_second_model=not large_model_available,
            require_human_validation=True,
            reinforced_tests=True,
            reasons=[f"risk_{risk}_requires_capability_and_human_signoff"],
        )

    confidence = prior_confidence if prior_confidence is not None else _DIFFICULTY_CONFIDENCE[difficulty]
    conf_source = "measured_prior" if prior_confidence is not None else "difficulty_estimate"

    if confidence >= target_confidence:
        return _strategy(
            "small_single",
            requested_tier="small",
            samples=1,
            use_deterministic_tool=use_python,
            reasons=[f"high_confidence_{conf_source}_early_stop"],
        )

    if confidence >= target_confidence * 0.7:
        return _strategy(
            "small_self_consistency",
            requested_tier="small",
            samples=3,
            weighted_vote=True,
            use_self_consistency=True,
            use_deterministic_tool=use_python,
            reasons=[f"medium_confidence_{conf_source}_weighted_vote"],
        )

    # Low confidence: lean on independent truth — a deterministic tool, a second
    # model, and an adversarial critique — not just more samples of the same model.
    return _strategy(
        "small_tool_second_model_critique",
        requested_tier="small",
        samples=3,
        weighted_vote=True,
        use_self_consistency=True,
        use_deterministic_tool=use_python,
        use_adversarial_critique=True,
        escalate_to_second_model=True,
        reasons=[f"low_confidence_{conf_source}_external_verification"],
    )


def _strategy(
    name: str,
    *,
    requested_tier: str,
    samples: int,
    weighted_vote: bool = False,
    use_self_consistency: bool = False,
    use_deterministic_tool: bool = False,
    use_adversarial_critique: bool = False,
    escalate_to_second_model: bool = False,
    require_human_validation: bool = False,
    reinforced_tests: bool = False,
    reasons: list[str],
) -> dict[str, object]:
    expected_calls = (
        samples
        + (1 if escalate_to_second_model else 0)
        + (1 if use_adversarial_critique else 0)
    )
    return {
        "policy_type": _POLICY_TYPE,
        "strategy": name,
        "requested_tier": requested_tier,
        "samples": samples,
        "weighted_vote": weighted_vote,
        "use_self_consistency": use_self_consistency,
        "use_deterministic_tool": use_deterministic_tool,
        "use_adversarial_critique": use_adversarial_critique,
        "escalate_to_second_model": escalate_to_second_model,
        "require_human_validation": require_human_validation,
        "reinforced_tests": reinforced_tests,
        "expected_model_calls": expected_calls,
        "model_call_performed": False,
        "reasons": reasons,
        "next_action": "execute_strategy",
    }
