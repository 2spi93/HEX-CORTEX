from hex_cortex.memory.world_state_candidate import (
    WorldStateCandidateJsonlStore,
    WorldStateCandidateRecord,
)
from hex_cortex.memory.world_state_candidate_evaluation import (
    evaluate_latest_world_state_candidate,
)
from hex_cortex.memory.world_state_skill_score import (
    score_latest_world_state_skill,
    summarize_world_state_skill_scores,
)


def test_world_state_skill_score_handles_missing_candidate(tmp_path) -> None:
    payload = score_latest_world_state_skill(tmp_path / "profile")
    record = payload["score_record"]

    assert record["suggested_skill"] == "world_state_builder"
    assert record["skill_score"] == 0.2


def test_world_state_skill_score_uses_valid_candidate(tmp_path) -> None:
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
    evaluate_latest_world_state_candidate(profile)

    payload = score_latest_world_state_skill(profile)
    summary = summarize_world_state_skill_scores(
        profile / "world-state-skill-score.jsonl"
    )
    record = payload["score_record"]

    assert record["suggested_skill"] == "operator_watch_review"
    assert record["skill_score"] == 1.0
    assert record["skill_reason"] == "low_risk_high_confidence_world_candidate"
    assert summary["latest_suggested_skill"] == "operator_watch_review"
