from hex_cortex.memory.controlled_skill_gate import evaluate_controlled_skill_gate
from hex_cortex.memory.planner_decision_packet import (
    PlannerDecisionPacketJsonlStore,
    PlannerDecisionPacketRecord,
)
from hex_cortex.memory.planner_replay_learning import (
    PlannerReplayLearningJsonlStore,
    PlannerReplayLearningRecord,
)


def test_controlled_skill_gate_blocks_missing_packet(tmp_path) -> None:
    payload = evaluate_controlled_skill_gate(tmp_path / "profile")
    record = payload["gate_record"]

    assert record["gate_decision"] == "gate_blocked"
    assert record["execution_allowed"] is False
    assert record["next_action"] == "build_planner_decision_packet"


def test_controlled_skill_gate_watches_planner_fallback(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_packet(profile, decision="planner_watch", status="watch", allowed=False)
    _write_replay(profile, recommendation="register_or_activate_missing_skills")

    payload = evaluate_controlled_skill_gate(profile)
    record = payload["gate_record"]

    assert record["gate_decision"] == "gate_watch"
    assert record["execution_allowed"] is False
    assert record["next_action"] == "register_or_activate_skill"


def test_controlled_skill_gate_allows_ready_staging(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_packet(profile, decision="planner_ready", status="ready", allowed=True)
    _write_replay(profile, recommendation="stage_controlled_skill_execution_gate")

    payload = evaluate_controlled_skill_gate(profile)
    record = payload["gate_record"]

    assert record["gate_decision"] == "gate_ready"
    assert record["execution_allowed"] is True
    assert record["execution_mode"] == "controlled_staging_only"


def _write_packet(profile, *, decision: str, status: str, allowed: bool) -> None:
    PlannerDecisionPacketJsonlStore(profile / "planner-decision-packet.jsonl").append(
        PlannerDecisionPacketRecord(
            profile_path=str(profile),
            source_latent_id="latent_a",
            source_match_id="match_a",
            source_cost_id="cost_a",
            selected_skill="operator_watch_review",
            selected_action="review_watch_reasons",
            planner_status=status,
            planner_decision=decision,
            next_action="register_or_activate_skill",
            action_allowed=allowed,
            registry_status="matched" if allowed else "fallback",
            match_score=0.82 if allowed else 0.4125,
            action_score=0.825,
            compression_score=0.8812,
            overall_confidence=0.8421 if allowed else 0.7062,
            reasons=["test_packet"],
        )
    )


def _write_replay(profile, *, recommendation: str) -> None:
    PlannerReplayLearningJsonlStore(profile / "planner-replay-learning.jsonl").append(
        PlannerReplayLearningRecord(
            profile_path=str(profile),
            packet_count=1,
            ready_count=1 if recommendation.startswith("stage_") else 0,
            watch_count=0 if recommendation.startswith("stage_") else 1,
            blocked_count=0,
            fallback_count=0 if recommendation.startswith("stage_") else 1,
            dominant_status="ready" if recommendation.startswith("stage_") else "watch",
            missing_skills=[] if recommendation.startswith("stage_") else ["operator_watch_review"],
            repeated_next_actions=[],
            latest_planner_decision="planner_ready" if recommendation.startswith("stage_") else "planner_watch",
            latest_next_action="stage_controlled_skill_execution_gate",
            replay_recommendation=recommendation,
            replay_score=1.0 if recommendation.startswith("stage_") else 0.8,
            reasons=["test_replay"],
        )
    )
