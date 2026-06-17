from hex_cortex.memory.action_cost_model import (
    estimate_latest_action_cost,
    summarize_action_costs,
)
from hex_cortex.memory.world_state_skill_score import (
    WorldStateSkillScoreJsonlStore,
    WorldStateSkillScoreRecord,
)


def test_action_cost_model_handles_missing_skill_score(tmp_path) -> None:
    payload = estimate_latest_action_cost(tmp_path / "profile")
    record = payload["cost_record"]

    assert record["verdict"] == "action_cost_missing_skill_score"
    assert record["action_score"] == 0.2


def test_action_cost_model_scores_low_cost_skill(tmp_path) -> None:
    profile = tmp_path / "profile"
    WorldStateSkillScoreJsonlStore(profile / "world-state-skill-score.jsonl").append(
        WorldStateSkillScoreRecord(
            profile_path=str(profile),
            candidate_id="world_a",
            evaluation_id="eval_a",
            candidate_action="review_watch_reasons",
            suggested_skill="operator_watch_review",
            skill_score=1.0,
            skill_reason="low_risk_high_confidence_world_candidate",
            world_verdict="world_candidate_valid",
            predicted_risk="low",
            predicted_cost=0.2,
            confidence=1.0,
        )
    )

    payload = estimate_latest_action_cost(profile)
    summary = summarize_action_costs(profile / "action-cost.jsonl")
    record = payload["cost_record"]

    assert record["overall_cost"] == 0.175
    assert record["action_score"] == 0.825
    assert record["verdict"] == "action_cost_valid"
    assert summary["latest_verdict"] == "action_cost_valid"
