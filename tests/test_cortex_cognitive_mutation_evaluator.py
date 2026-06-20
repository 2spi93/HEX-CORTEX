from hex_cortex.memory.cortex_cognitive_genome import evaluate_mutation_candidate


def test_mutation_with_changed_evaluator_is_rejected() -> None:
    payload = evaluate_mutation_candidate(
        plan_hash="a" * 64,
        critical_competency_deltas={"critical": 0.0},
        noncritical_competency_deltas={},
        target_skill_delta=0.2,
        heldout_passed=True,
        reversible=True,
        evaluator_changed=True,
        threshold_lowered=False,
    )

    assert payload["status"] == "rejected"
    assert "evaluator_changed" in payload["blockers"]
