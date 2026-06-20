from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome import audit_cognitive_genome
from hex_cortex.memory.cortex_cognitive_genome import build_mutation_plan
from hex_cortex.memory.cortex_cognitive_genome import evaluate_mutation_candidate


def test_cognitive_genome_remains_immutable_and_weight_safe() -> None:
    audit = audit_cognitive_genome(Path("config/cognitive_genome_v1.json"))
    plan = build_mutation_plan(
        skill_candidate_hash="a" * 64,
        mutation_level="full_weight_update",
        baseline_ref="baseline",
        evaluator_ref="evaluator",
        revocation_ref="revocation",
    )

    assert audit["genome_ready"] is True
    assert audit["base_model_immutable"] is True
    assert plan["status"] == "blocked"
    assert "full_weight_update_disabled" in plan["blockers"]


def test_anti_forgetting_still_rejects_critical_regression() -> None:
    result = evaluate_mutation_candidate(
        plan_hash="b" * 64,
        critical_competency_deltas={"architecture_contracts": -0.001},
        noncritical_competency_deltas={},
        target_skill_delta=0.2,
        heldout_passed=True,
        reversible=True,
        evaluator_changed=False,
        threshold_lowered=False,
    )

    assert result["status"] == "rejected"
    assert result["anti_forgetting_passed"] is False
