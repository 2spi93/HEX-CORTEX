import json
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome import append_cognitive_residual
from hex_cortex.memory.cortex_cognitive_genome import audit_cognitive_genome
from hex_cortex.memory.cortex_cognitive_genome import build_cr_jepa_v0_manifest
from hex_cortex.memory.cortex_cognitive_genome import build_homeostasis_decision
from hex_cortex.memory.cortex_cognitive_genome import build_mutation_plan
from hex_cortex.memory.cortex_cognitive_genome import build_profile_council
from hex_cortex.memory.cortex_cognitive_genome import build_skill_candidate
from hex_cortex.memory.cortex_cognitive_genome import evaluate_mutation_candidate
from hex_cortex.memory.cortex_cognitive_genome import project_residual_topology


def test_repository_cognitive_genome_is_ready() -> None:
    payload = audit_cognitive_genome(Path("config/cognitive_genome_v1.json"))

    assert payload["genome_ready"] is True
    assert payload["base_model_immutable"] is True
    assert payload["full_weight_update_enabled"] is False
    assert payload["cr_jepa_v0_present"] is True
    assert payload["blockers"] == []


def test_residual_ledger_persists_hashes_not_raw_reasoning(tmp_path: Path) -> None:
    ledger = tmp_path / "residuals.jsonl"
    payload = append_cognitive_residual(
        ledger,
        model_id="local-model-secret-label",
        model_family="gemma",
        domain="hex-cortex",
        context_signature="context-with-private-details",
        state_embedding_ref="state-vector-ref",
        predicted_outcome_ref="predicted-vector-ref",
        observed_outcome_ref="observed-vector-ref",
        failure_class="planning_error",
        residual_magnitude=0.42,
        profile_set=["scientist", "engineer"],
        tool_set=["pytest"],
        correction_ref="verified-fix-reference",
        correction_verified=True,
        causal_intervention_verified=True,
        best_corrective_intervention="run_deterministic_verifier",
    )

    persisted = ledger.read_text(encoding="utf-8")
    assert payload["record_type"] == "cognitive_residual_record_v1"
    assert payload["raw_reasoning_persisted"] is False
    assert "local-model-secret-label" not in persisted
    assert "context-with-private-details" not in persisted
    assert "verified-fix-reference" not in persisted
    assert "state-vector-ref" not in persisted


def test_residual_topology_requires_recurrence_models_contexts_and_causality(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "residuals.jsonl"
    for index, model_id in enumerate(("model-a", "model-b", "model-a")):
        append_cognitive_residual(
            ledger,
            model_id=model_id,
            model_family="local",
            domain="hex-cortex",
            context_signature=f"context-{index % 2}",
            state_embedding_ref=f"state-{index}",
            predicted_outcome_ref=f"predicted-{index}",
            observed_outcome_ref=f"observed-{index}",
            failure_class="planning_error",
            residual_magnitude=0.5 + index * 0.1,
            profile_set=["scientist", "engineer"],
            tool_set=["pytest"],
            correction_ref=f"fix-{index}",
            correction_verified=True,
            causal_intervention_verified=index == 2,
            best_corrective_intervention="run_deterministic_verifier",
        )

    topology = project_residual_topology(ledger)

    assert topology["residual_count"] == 3
    assert topology["cluster_count"] == 1
    assert topology["consolidation_ready_count"] == 1
    cluster = topology["clusters"][0]
    assert cluster["distinct_model_count"] == 2
    assert cluster["distinct_context_count"] == 2
    assert cluster["skill_consolidation_ready"] is True

    candidate = build_skill_candidate(
        topology,
        residual_signature=cluster["residual_signature"],
        skill_id="planning-verifier-v1",
        domain="hex-cortex",
    )
    assert candidate["status"] == "candidate"
    assert candidate["adapter_training_allowed"] is True
    assert candidate["promotion_allowed"] is False


def test_profile_council_uses_epistemic_roles_not_majority_vote() -> None:
    payload = build_profile_council(
        failure_class="causal_misattribution",
        novelty=0.8,
        uncertainty=0.9,
        mutation_requested=True,
    )

    assert "causalist" in payload["selected_profiles"]
    assert "explorer" in payload["selected_profiles"]
    assert "constitutional_judge" in payload["selected_profiles"]
    assert payload["majority_vote_allowed"] is False
    assert payload["evidence_weighted_adjudication_required"] is True


def test_homeostasis_escalates_but_does_not_mutate_weights() -> None:
    payload = build_homeostasis_decision(
        uncertainty=0.9,
        recurrence_count=4,
        deterministic_verification_available=False,
        local_verification_failed=True,
        cost_pressure=0.2,
        regression_risk=0.1,
    )

    assert "consult_remote_teacher" in payload["selected_actions"]
    assert "propose_skill_consolidation" in payload["selected_actions"]
    assert "consider_isolated_adapter_candidate" in payload["selected_actions"]
    assert "refuse_unverified_action" in payload["selected_actions"]
    assert payload["weight_mutation_selected"] is False


def test_full_weight_mutation_is_disabled() -> None:
    payload = build_mutation_plan(
        skill_candidate_hash="a" * 64,
        mutation_level="full_weight_update",
        baseline_ref="baseline-v1",
        evaluator_ref="evaluator-v1",
        revocation_ref="revoke-v1",
    )

    assert payload["status"] == "blocked"
    assert payload["base_model_immutable"] is True
    assert "full_weight_update_disabled" in payload["blockers"]


def test_isolated_adapter_plan_is_reversible_and_heldout_gated() -> None:
    payload = build_mutation_plan(
        skill_candidate_hash="b" * 64,
        mutation_level="isolated_adapter_candidate",
        baseline_ref="baseline-v1",
        evaluator_ref="evaluator-v1",
        revocation_ref="adapter-revoke-v1",
    )

    assert payload["status"] == "ready"
    assert payload["isolated_adapter_required"] is True
    assert payload["heldout_required"] is True
    assert payload["automatic_merge_allowed"] is False


def test_anti_forgetting_rejects_critical_regression() -> None:
    payload = evaluate_mutation_candidate(
        plan_hash="c" * 64,
        critical_competency_deltas={"architecture_contracts": -0.001},
        noncritical_competency_deltas={"style": 0.1},
        target_skill_delta=0.2,
        heldout_passed=True,
        reversible=True,
        evaluator_changed=False,
        threshold_lowered=False,
    )

    assert payload["status"] == "rejected"
    assert payload["anti_forgetting_passed"] is False
    assert "critical_competency_regressed:architecture_contracts" in payload["blockers"]


def test_anti_forgetting_allows_verified_reversible_improvement() -> None:
    payload = evaluate_mutation_candidate(
        plan_hash="d" * 64,
        critical_competency_deltas={"architecture_contracts": 0.0},
        noncritical_competency_deltas={"style": -0.01},
        target_skill_delta=0.2,
        heldout_passed=True,
        reversible=True,
        evaluator_changed=False,
        threshold_lowered=False,
    )

    assert payload["status"] == "promotable"
    assert payload["anti_forgetting_passed"] is True
    assert payload["promotion_allowed"] is True
    assert payload["merge_performed"] is False


def test_cr_jepa_v0_is_dataset_only_until_research_gate(tmp_path: Path) -> None:
    ledger = tmp_path / "residuals.jsonl"
    append_cognitive_residual(
        ledger,
        model_id="model-a",
        model_family="local",
        domain="hex-cortex",
        context_signature="context-a",
        state_embedding_ref="state-a",
        predicted_outcome_ref="predicted-a",
        observed_outcome_ref="observed-a",
        failure_class="logic_error",
        residual_magnitude=0.2,
        profile_set=["scientist"],
        tool_set=["pytest"],
        correction_ref="fix-a",
        correction_verified=True,
    )

    payload = build_cr_jepa_v0_manifest(ledger)

    assert payload["manifest_type"] == "cognitive_residual_jepa_dataset_manifest_v0"
    assert payload["training_allowed"] is False
    assert payload["verified_residual_count"] == 1
    assert payload["raw_reasoning_required"] is False
    assert json.dumps(payload).find("fix-a") == -1
