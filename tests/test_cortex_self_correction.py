from hex_cortex.memory.cortex_self_correction import build_self_correction_plan
from hex_cortex.memory.cortex_self_correction import evaluate_repair_candidate


def test_self_correction_plan_is_bounded_and_fail_closed() -> None:
    payload = build_self_correction_plan(
        failure_class="policy_gate_failed",
        hypothesis="Spatial patch pooling improves action ranking.",
        baseline_ref="main@abc123",
        evaluator_ref="screen_lab_policy_v2_gate",
    )

    assert payload["status"] == "ready"
    assert payload["hypothesis_mutation_allowed"] is False
    assert payload["evaluator_mutation_allowed"] is False
    assert payload["threshold_reduction_allowed"] is False
    assert payload["operator_merge_approval_required"] is True


def test_repair_candidate_rejects_evaluator_tampering() -> None:
    plan = build_self_correction_plan(
        failure_class="test_failure",
        hypothesis="Fix one parser edge case.",
        baseline_ref="main@abc123",
        evaluator_ref="pytest",
    )
    payload = evaluate_repair_candidate(
        plan_hash=plan["plan_hash"],
        candidate_ref="worktree/candidate-1",
        deterministic_checks_passed=True,
        task_metric_improved=True,
        heldout_gate_passed=True,
        evaluator_changed=True,
        files_changed=2,
    )

    assert payload["status"] == "rejected"
    assert payload["candidate_promotable"] is False
    assert "evaluator_changed" in payload["blockers"]


def test_repair_candidate_can_request_operator_merge() -> None:
    plan = build_self_correction_plan(
        failure_class="test_failure",
        hypothesis="Fix one parser edge case.",
        baseline_ref="main@abc123",
        evaluator_ref="pytest",
    )
    payload = evaluate_repair_candidate(
        plan_hash=plan["plan_hash"],
        candidate_ref="worktree/candidate-1",
        deterministic_checks_passed=True,
        task_metric_improved=True,
        heldout_gate_passed=True,
        files_changed=2,
    )

    assert payload["status"] == "promotable"
    assert payload["merge_allowed"] is True
    assert payload["merge_performed"] is False
