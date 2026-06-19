from pathlib import Path

from hex_cortex.memory.cortex_research_hypothesis_ledger import append_research_hypothesis
from hex_cortex.memory.cortex_research_hypothesis_ledger import append_research_outcome
from hex_cortex.memory.cortex_research_hypothesis_ledger import project_research_frontier


def test_research_hypothesis_tree_tracks_parent_child_and_frontier(tmp_path: Path) -> None:
    path = tmp_path / "hypotheses.jsonl"
    root = append_research_hypothesis(
        path,
        statement="Spatial patch pooling improves action ranking.",
        baseline_ref="main@abc123",
        evaluator_ref="screen_lab_policy_v2_gate",
        created_by="hex-cortex",
    )
    child = append_research_hypothesis(
        path,
        statement="Quadrant pooling is sufficient for the first improvement.",
        baseline_ref="main@abc123",
        evaluator_ref="screen_lab_policy_v2_gate",
        created_by="hex-cortex",
        parent_id=root["hypothesis_id"],
    )

    projection = project_research_frontier(path)

    assert projection["node_count"] == 2
    assert projection["frontier_count"] == 2
    assert child["depth"] == 1
    assert projection["selected_next_hypothesis_id"] == root["hypothesis_id"]


def test_validated_outcome_requires_positive_heldout_result(tmp_path: Path) -> None:
    path = tmp_path / "hypotheses.jsonl"
    node = append_research_hypothesis(
        path,
        statement="Ranking loss improves test top-1.",
        baseline_ref="main@abc123",
        evaluator_ref="heldout-v2",
        created_by="hex-cortex",
    )
    outcome = append_research_outcome(
        path,
        hypothesis_id=node["hypothesis_id"],
        status="validated",
        candidate_ref="candidate-1",
        metric_delta=0.25,
        heldout_passed=True,
        insight_ref="insight-1",
    )
    projection = project_research_frontier(path)

    assert outcome["merge_allowed"] is True
    assert outcome["merge_performed"] is False
    assert projection["best_validated_hypothesis_id"] == node["hypothesis_id"]
    assert projection["frontier_count"] == 0


def test_rejected_outcome_is_not_mergeable(tmp_path: Path) -> None:
    path = tmp_path / "hypotheses.jsonl"
    node = append_research_hypothesis(
        path,
        statement="A weak idea.",
        baseline_ref="main@abc123",
        evaluator_ref="heldout-v2",
        created_by="hex-cortex",
    )
    outcome = append_research_outcome(
        path,
        hypothesis_id=node["hypothesis_id"],
        status="rejected",
        candidate_ref="candidate-2",
        metric_delta=-0.1,
        heldout_passed=False,
    )

    assert outcome["merge_allowed"] is False
