from hex_cortex.memory.cortex_cognitive_genome import build_homeostasis_decision
from hex_cortex.memory.cortex_cognitive_genome import build_mutation_plan


def test_homeostasis_never_selects_direct_weight_mutation() -> None:
    payload = build_homeostasis_decision(
        uncertainty=1.0,
        recurrence_count=100,
        deterministic_verification_available=False,
        local_verification_failed=True,
        cost_pressure=0.0,
        regression_risk=0.0,
    )

    assert payload["weight_mutation_selected"] is False
    assert payload["reversible_path_only"] is True


def test_full_weight_plan_is_fail_closed_even_with_valid_refs() -> None:
    payload = build_mutation_plan(
        skill_candidate_hash="f" * 64,
        mutation_level="full_weight_update",
        baseline_ref="baseline",
        evaluator_ref="evaluator",
        revocation_ref="revocation",
    )

    assert payload["status"] == "blocked"
    assert payload["base_model_immutable"] is True
