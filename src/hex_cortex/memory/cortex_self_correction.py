from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class RepairBudget:
    max_attempts: int = 2
    max_files_changed: int = 12
    max_runtime_seconds: int = 1800


def build_self_correction_plan(
    *,
    failure_class: str,
    hypothesis: str,
    baseline_ref: str,
    evaluator_ref: str,
    budget: RepairBudget | None = None,
) -> dict[str, object]:
    selected_budget = budget or RepairBudget()
    blockers = []
    for label, value in {
        "failure_class": failure_class,
        "hypothesis": hypothesis,
        "baseline_ref": baseline_ref,
        "evaluator_ref": evaluator_ref,
    }.items():
        if not value.strip():
            blockers.append(f"{label}_missing")
    if selected_budget.max_attempts < 1 or selected_budget.max_attempts > 5:
        blockers.append("max_attempts_out_of_range")
    if selected_budget.max_files_changed < 1 or selected_budget.max_files_changed > 50:
        blockers.append("max_files_changed_out_of_range")
    if selected_budget.max_runtime_seconds < 30 or selected_budget.max_runtime_seconds > 7200:
        blockers.append("max_runtime_seconds_out_of_range")

    payload = {
        "plan_type": "self_correction_hypothesis_loop_v1",
        "status": "ready" if not blockers else "blocked",
        "failure_class": failure_class,
        "hypothesis": hypothesis,
        "hypothesis_mutation_allowed": False,
        "baseline_ref": baseline_ref,
        "evaluator_ref": evaluator_ref,
        "evaluator_mutation_allowed": False,
        "threshold_reduction_allowed": False,
        "history_rewrite_allowed": False,
        "worktree_required": True,
        "operator_merge_approval_required": True,
        "budget": {
            "max_attempts": selected_budget.max_attempts,
            "max_files_changed": selected_budget.max_files_changed,
            "max_runtime_seconds": selected_budget.max_runtime_seconds,
        },
        "steps": [
            "create_isolated_worktree",
            "produce_bounded_patch",
            "run_allowlisted_checks",
            "classify_result",
            "repair_within_budget",
            "compare_to_baseline_and_siblings",
            "run_heldout_gate",
            "emit_receipt",
            "request_operator_merge",
        ],
        "execution_performed": False,
        "merge_performed": False,
        "blockers": blockers,
        "next_action": "create_isolated_worktree" if not blockers else "repair_correction_plan_inputs",
    }
    payload["plan_hash"] = _stable_hash(payload)
    return payload


def evaluate_repair_candidate(
    *,
    plan_hash: str,
    candidate_ref: str,
    deterministic_checks_passed: bool,
    task_metric_improved: bool,
    heldout_gate_passed: bool,
    evaluator_changed: bool = False,
    threshold_lowered: bool = False,
    files_changed: int = 0,
    attempt_index: int = 1,
    budget: RepairBudget | None = None,
) -> dict[str, object]:
    selected_budget = budget or RepairBudget()
    blockers = []
    if len(plan_hash) != 64:
        blockers.append("plan_hash_invalid")
    if not candidate_ref.strip():
        blockers.append("candidate_ref_missing")
    if evaluator_changed:
        blockers.append("evaluator_changed")
    if threshold_lowered:
        blockers.append("threshold_lowered")
    if attempt_index < 1 or attempt_index > selected_budget.max_attempts:
        blockers.append("repair_attempt_budget_exceeded")
    if files_changed < 0 or files_changed > selected_budget.max_files_changed:
        blockers.append("files_changed_budget_exceeded")
    if not deterministic_checks_passed:
        blockers.append("deterministic_checks_failed")
    if not task_metric_improved:
        blockers.append("task_metric_not_improved")
    if not heldout_gate_passed:
        blockers.append("heldout_gate_failed")

    promotable = not blockers
    payload = {
        "evaluation_type": "self_correction_candidate_evaluation_v1",
        "status": "promotable" if promotable else "rejected",
        "plan_hash": plan_hash,
        "candidate_ref": candidate_ref,
        "attempt_index": attempt_index,
        "files_changed": files_changed,
        "deterministic_checks_passed": deterministic_checks_passed,
        "task_metric_improved": task_metric_improved,
        "heldout_gate_passed": heldout_gate_passed,
        "evaluator_changed": evaluator_changed,
        "threshold_lowered": threshold_lowered,
        "candidate_promotable": promotable,
        "merge_allowed": promotable,
        "merge_performed": False,
        "operator_merge_approval_required": True,
        "blockers": blockers,
        "next_action": "request_operator_merge" if promotable else "retain_failed_attempt_as_evidence",
    }
    payload["evaluation_hash"] = _stable_hash(payload)
    return payload


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
