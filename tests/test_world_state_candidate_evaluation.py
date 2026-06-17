from hex_cortex.memory.world_state_candidate import (
    WorldStateCandidateJsonlStore,
    WorldStateCandidateRecord,
)
from hex_cortex.memory.world_state_candidate_evaluation import (
    evaluate_latest_world_state_candidate,
    summarize_world_state_candidate_evaluations,
)


def test_world_state_candidate_evaluation_blocks_missing_candidate(tmp_path) -> None:
    payload = evaluate_latest_world_state_candidate(tmp_path / "profile")
    record = payload["evaluation_record"]

    assert record["verdict"] == "world_candidate_missing"
    assert record["overall_score"] == 0.0


def test_world_state_candidate_evaluation_scores_valid_candidate(tmp_path) -> None:
    profile = tmp_path / "profile"
    WorldStateCandidateJsonlStore(profile / "world-state-candidate.jsonl").append(
        WorldStateCandidateRecord(
            profile_path=str(profile),
            trace_id="trace_a",
            evaluation_id="eval_a",
            current_state="status=watch; decision=watch",
            expected_state="operator_reviews_watch_reasons",
            candidate_action="review_watch_reasons",
            predicted_risk="low",
            predicted_cost=0.2,
            confidence=1.0,
            source_verdict="trace_valid",
        )
    )

    payload = evaluate_latest_world_state_candidate(profile)
    summary = summarize_world_state_candidate_evaluations(
        profile / "world-state-candidate-evaluation.jsonl"
    )
    record = payload["evaluation_record"]

    assert record["verdict"] == "world_candidate_valid"
    assert record["overall_score"] == 1.0
    assert summary["latest_verdict"] == "world_candidate_valid"
