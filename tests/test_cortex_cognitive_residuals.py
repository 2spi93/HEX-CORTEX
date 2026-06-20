from pathlib import Path

from hex_cortex.memory.cortex_cognitive_residuals import append_cognitive_residual
from hex_cortex.memory.cortex_cognitive_residuals import build_residual_signature
from hex_cortex.memory.cortex_cognitive_residuals import project_residual_topology


def test_signature_is_context_and_model_independent() -> None:
    first = build_residual_signature(
        failure_class="planning_error",
        domain="hex-cortex",
        best_corrective_intervention="run_verifier",
    )
    second = build_residual_signature(
        failure_class="planning_error",
        domain="hex-cortex",
        best_corrective_intervention="run_verifier",
    )

    assert first == second


def test_topology_groups_same_failure_across_contexts_and_models(tmp_path: Path) -> None:
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
            residual_magnitude=0.4 + index * 0.1,
            profile_set=["scientist", "engineer"],
            tool_set=["pytest"],
            correction_ref=f"fix-{index}",
            correction_verified=True,
            causal_intervention_verified=index == 2,
            best_corrective_intervention="run_verifier",
        )

    payload = project_residual_topology(ledger)

    assert payload["cluster_count"] == 1
    assert payload["consolidation_ready_count"] == 1
    cluster = payload["clusters"][0]
    assert cluster["occurrence_count"] == 3
    assert cluster["distinct_context_count"] == 2
    assert cluster["distinct_model_count"] == 2
    assert cluster["skill_consolidation_ready"] is True
