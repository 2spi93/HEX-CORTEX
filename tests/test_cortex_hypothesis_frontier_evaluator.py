from hex_cortex.memory.cortex_hypothesis_frontier_evaluator import (
    CORTEX_HYPOTHESIS_FRONTIER_EVALUATOR_FILENAME,
    build_cortex_hypothesis_frontier_evaluator,
    summarize_cortex_hypothesis_frontier_evaluators,
)
from hex_cortex.memory.cortex_hypothesis_tree import (
    CORTEX_HYPOTHESIS_TREE_FILENAME,
    CortexHypothesisNode,
    CortexHypothesisTreeJsonlStore,
    CortexHypothesisTreeRecord,
)


def _tree(profile, **overrides):
    root = CortexHypothesisNode(
        node_id="root:memory_first",
        parent_id=None,
        depth=0,
        hypothesis="A small memory-first subsystem is the best next branch.",
        node_status="root",
        score=0.9,
        source_block_ids=["state:build_choice"],
        latent_state="memory-first build state",
        predicted_future="selector then evaluation before broader routing",
        cost_estimate="low",
    )
    frontier_state = CortexHypothesisNode(
        node_id="frontier:state:build_choice",
        parent_id=root.node_id,
        depth=1,
        hypothesis="Use state block as evidence.",
        node_status="frontier",
        score=1.0,
        source_block_ids=["state:build_choice"],
        latent_state="current abstract state",
        predicted_future="next memory step",
        cost_estimate="prefer small verified steps",
    )
    frontier_rule = CortexHypothesisNode(
        node_id="frontier:rule:active_frame",
        parent_id=root.node_id,
        depth=1,
        hypothesis="Use rule block as evidence.",
        node_status="frontier",
        score=0.95,
        source_block_ids=["rule:active_frame"],
        latent_state="compressed reusable rule",
        predicted_future="keeps memory-first trajectory",
        cost_estimate="limits context and drift",
    )
    payload = {
        "profile_path": str(profile),
        "source_selector_id": "selector_1",
        "source_selector_hash": "a" * 64,
        "tree_status": "ready",
        "tree_decision": "hypothesis_tree_ready",
        "tree_allowed": True,
        "root_node_id": root.node_id,
        "frontier_node_ids": [frontier_state.node_id, frontier_rule.node_id],
        "node_count": 3,
        "nodes": [root, frontier_state, frontier_rule],
        "next_action": "evaluate_hypothesis_frontier",
        "blockers": [],
        "tree_hash": "b" * 64,
        "reasons": ["selector_ready"],
    }
    payload.update(overrides)
    record = CortexHypothesisTreeRecord(**payload)
    CortexHypothesisTreeJsonlStore(profile / CORTEX_HYPOTHESIS_TREE_FILENAME).save([record])
    return record


def test_frontier_evaluator_scores_and_selects_best_node(tmp_path) -> None:
    profile = tmp_path / "profile"
    _tree(profile)

    record = build_cortex_hypothesis_frontier_evaluator(profile)["evaluator_records"][0]

    assert record["evaluator_allowed"] is True
    assert record["evaluator_status"] == "ready"
    assert record["evaluator_decision"] == "hypothesis_frontier_evaluator_ready"
    assert record["frontier_count"] == 2
    assert record["best_node_id"] == "frontier:state:build_choice"
    assert record["next_action"] == "prepare_frontier_branch_plan"
    assert len(record["evaluator_hash"]) == 64


def test_frontier_evaluator_blocks_when_tree_blocked(tmp_path) -> None:
    profile = tmp_path / "profile"
    _tree(
        profile,
        tree_allowed=False,
        tree_decision="hypothesis_tree_blocked",
        tree_status="blocked",
        next_action="repair_memory_retrieval_selector",
        blockers=["memory_retrieval_selector_not_allowed"],
    )

    record = build_cortex_hypothesis_frontier_evaluator(profile)["evaluator_records"][0]

    assert record["evaluator_allowed"] is False
    assert "hypothesis_tree_not_allowed" in record["blockers"]


def test_frontier_evaluator_is_idempotent_by_tree_hash(tmp_path) -> None:
    profile = tmp_path / "profile"
    _tree(profile)

    first = build_cortex_hypothesis_frontier_evaluator(profile)
    second = build_cortex_hypothesis_frontier_evaluator(profile)

    assert len(first["evaluator_records"]) == 1
    assert second["evaluator_records"] == []
    assert second["evaluator_count"] == 1


def test_frontier_evaluator_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _tree(profile)
    build_cortex_hypothesis_frontier_evaluator(profile)

    summary = summarize_cortex_hypothesis_frontier_evaluators(
        profile / CORTEX_HYPOTHESIS_FRONTIER_EVALUATOR_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_hypothesis_frontier_evaluator"
    assert summary["total_evaluator_count"] == 1
    assert summary["allowed_evaluator_count"] == 1
    assert summary["latest_evaluator_allowed"] is True
    assert summary["latest_best_node_id"] == "frontier:state:build_choice"
    assert summary["latest_next_action"] == "prepare_frontier_branch_plan"
