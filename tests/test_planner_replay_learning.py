from hex_cortex.memory.planner_decision_packet import (
    PlannerDecisionPacketJsonlStore,
    PlannerDecisionPacketRecord,
)
from hex_cortex.memory.planner_replay_learning import (
    learn_from_planner_packets,
    summarize_planner_replay_learning,
)


def test_planner_replay_learning_handles_missing_packets(tmp_path) -> None:
    payload = learn_from_planner_packets(tmp_path / "profile")
    record = payload["replay_record"]

    assert record["replay_recommendation"] == "build_planner_decision_packet"
    assert record["replay_score"] == 0.0


def test_planner_replay_learning_detects_fallback_skill(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_packet(profile, status="watch", registry_status="fallback")

    payload = learn_from_planner_packets(profile)
    summary = summarize_planner_replay_learning(profile / "planner-replay-learning.jsonl")
    record = payload["replay_record"]

    assert record["fallback_count"] == 1
    assert record["missing_skills"] == ["operator_watch_review"]
    assert record["replay_recommendation"] == "register_or_activate_missing_skills"
    assert summary["latest_replay_recommendation"] == "register_or_activate_missing_skills"


def test_planner_replay_learning_detects_ready_packet(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_packet(profile, status="ready", registry_status="matched")

    payload = learn_from_planner_packets(profile)
    record = payload["replay_record"]

    assert record["ready_count"] == 1
    assert record["replay_recommendation"] == "stage_controlled_skill_execution_gate"
    assert record["replay_score"] == 1.0


def _write_packet(profile, *, status: str, registry_status: str) -> None:
    PlannerDecisionPacketJsonlStore(profile / "planner-decision-packet.jsonl").append(
        PlannerDecisionPacketRecord(
            profile_path=str(profile),
            source_latent_id="latent_a",
            source_match_id="match_a",
            source_cost_id="cost_a",
            selected_skill="operator_watch_review",
            selected_action="review_watch_reasons",
            planner_status=status,
            planner_decision="planner_" + status,
            next_action="register_or_activate_skill",
            action_allowed=status == "ready",
            registry_status=registry_status,
            match_score=0.82 if registry_status == "matched" else 0.4125,
            action_score=0.825,
            compression_score=0.8812,
            overall_confidence=0.8421 if status == "ready" else 0.7062,
            reasons=["test_packet"],
        )
    )
