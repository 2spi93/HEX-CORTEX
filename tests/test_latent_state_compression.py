from hex_cortex.memory.action_cost_model import (
    ActionCostJsonlStore,
    ActionCostRecord,
)
from hex_cortex.memory.latent_state_compression import (
    compress_latest_latent_state,
    summarize_latent_states,
)
from hex_cortex.memory.world_state_candidate import (
    WorldStateCandidateJsonlStore,
    WorldStateCandidateRecord,
)
from hex_cortex.memory.world_state_skill_score import (
    WorldStateSkillScoreJsonlStore,
    WorldStateSkillScoreRecord,
)


def test_latent_state_compression_handles_missing_action_cost(tmp_path) -> None:
    payload = compress_latest_latent_state(tmp_path / "profile")
    record = payload["latent_record"]

    assert record["verdict"] == "latent_missing_action_cost"
    assert record["vector_dim"] == 8
    assert record["compression_score"] == 0.0


def test_latent_state_compression_compresses_valid_sources(tmp_path) -> None:
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
    ActionCostJsonlStore(profile / "action-cost.jsonl").append(
        ActionCostRecord(
            profile_path=str(profile),
            score_id="skill_score_a",
            suggested_skill="operator_watch_review",
            candidate_action="review_watch_reasons",
            cognitive_cost=0.2,
            operator_cost=0.2,
            risk_cost=0.1,
            time_cost=0.2,
            overall_cost=0.175,
            action_score=0.825,
            verdict="action_cost_valid",
            reasons=["action_cost_quality_ok"],
        )
    )

    payload = compress_latest_latent_state(profile)
    summary = summarize_latent_states(profile / "latent-state.jsonl")
    record = payload["latent_record"]

    assert record["verdict"] == "latent_state_valid"
    assert record["vector_dim"] == 8
    assert record["suggested_skill"] == "operator_watch_review"
    assert "skill:operator_watch_review" in record["tokens"]
    assert summary["latest_verdict"] == "latent_state_valid"
