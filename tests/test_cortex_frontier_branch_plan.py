from hex_cortex.memory.cortex_frontier_branch_plan import (
    CORTEX_FRONTIER_BRANCH_PLAN_FILENAME,
    build_cortex_frontier_branch_plan,
    summarize_cortex_frontier_branch_plans,
)
from hex_cortex.memory.cortex_hypothesis_frontier_evaluator import (
    CORTEX_HYPOTHESIS_FRONTIER_EVALUATOR_FILENAME,
    CortexHypothesisFrontierEvaluation,
    CortexHypothesisFrontierEvaluatorJsonlStore,
    CortexHypothesisFrontierEvaluatorRecord,
)


def _evaluator(profile):
    best = CortexHypothesisFrontierEvaluation(
        node_id="frontier:state:build_choice",
        hypothesis="Use the state block as evidence.",
        evidence_score=1.0,
        future_score=0.95,
        cost_score=0.95,
        total_score=0.9725,
        verdict="frontier_candidate_ready",
        source_block_ids=["state:build_choice"],
        latent_state="current abstract state",
        predicted_future="next memory step",
        cost_estimate="prefer small verified steps",
    )
    record = CortexHypothesisFrontierEvaluatorRecord(
        profile_path=str(profile),
        source_tree_id="tree_1",
        source_tree_hash="a" * 64,
        evaluator_status="ready",
        evaluator_decision="hypothesis_frontier_evaluator_ready",
        evaluator_allowed=True,
        frontier_count=1,
        evaluations=[best],
        best_node_id=best.node_id,
        best_total_score=best.total_score,
        next_action="prepare_frontier_branch_plan",
        blockers=[],
        evaluator_hash="b" * 64,
        reasons=["frontier_scored", "best_branch_selected"],
    )
    CortexHypothesisFrontierEvaluatorJsonlStore(
        profile / CORTEX_HYPOTHESIS_FRONTIER_EVALUATOR_FILENAME
    ).save([record])
    return record


def test_frontier_branch_plan_builds_from_ready_evaluator(tmp_path) -> None:
    profile = tmp_path / "profile"
    evaluator = _evaluator(profile)

    record = build_cortex_frontier_branch_plan(profile)["plan_records"][0]

    assert record["plan_allowed"] is True
    assert record["plan_status"] == "ready"
    assert record["plan_decision"] == "frontier_branch_plan_ready"
    assert record["source_evaluator_id"] == evaluator.evaluator_id
    assert record["best_node_id"] == "frontier:state:build_choice"
    assert record["target_branch_type"] == "memory_first_build_branch"
    assert record["next_action"] == "await_branch_plan_review"
    assert len(record["branch_steps"]) == 3
    assert len(record["plan_hash"]) == 64


def test_frontier_branch_plan_is_idempotent_by_evaluator_hash(tmp_path) -> None:
    profile = tmp_path / "profile"
    _evaluator(profile)

    first = build_cortex_frontier_branch_plan(profile)
    second = build_cortex_frontier_branch_plan(profile)

    assert len(first["plan_records"]) == 1
    assert second["plan_records"] == []
    assert second["plan_count"] == 1


def test_frontier_branch_plan_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _evaluator(profile)
    build_cortex_frontier_branch_plan(profile)

    summary = summarize_cortex_frontier_branch_plans(
        profile / CORTEX_FRONTIER_BRANCH_PLAN_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_frontier_branch_plan"
    assert summary["total_plan_count"] == 1
    assert summary["allowed_plan_count"] == 1
    assert summary["latest_plan_allowed"] is True
    assert summary["latest_best_node_id"] == "frontier:state:build_choice"
    assert summary["latest_target_branch_type"] == "memory_first_build_branch"
    assert summary["latest_next_action"] == "await_branch_plan_review"
