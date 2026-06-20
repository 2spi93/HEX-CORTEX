from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome import build_skill_candidate
from hex_cortex.memory.cortex_cognitive_residuals import append_cognitive_residual
from hex_cortex.memory.cortex_cognitive_residuals import project_residual_topology


def test_genome_v2_consolidates_cross_context_residuals(tmp_path: Path) -> None:
    ledger = tmp_path / "residuals.jsonl"
    for index, model_id in enumerate(("model-a", "model-b", "model-a")):
        append_cognitive_residual(
            ledger,
            model_id=model_id,
            model_family="local",
            domain="hex-cortex",
            context_signature=f"context-{index % 2}",
            state_embedding_ref=f"state-{index}",
            predicted_outcome_ref=f"prediction-{index}",
            observed_outcome_ref=f"observation-{index}",
            failure_class="planning_error",
            residual_magnitude=0.4,
            profile_set=["scientist", "engineer"],
            tool_set=["pytest"],
            correction_ref=f"fix-{index}",
            correction_verified=True,
            causal_intervention_verified=index == 2,
            best_corrective_intervention="run_verifier",
        )

    topology = project_residual_topology(ledger)
    assert topology["cluster_count"] == 1
    assert topology["consolidation_ready_count"] == 1
    cluster = topology["clusters"][0]
    candidate = build_skill_candidate(
        topology,
        residual_signature=cluster["residual_signature"],
        skill_id="planning-verifier-v1",
        domain="hex-cortex",
    )
    assert candidate["status"] == "candidate"
    assert candidate["adapter_training_allowed"] is True
