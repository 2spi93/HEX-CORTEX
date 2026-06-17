from hex_cortex.memory.action_cost_model import (
    ActionCostJsonlStore,
    ActionCostRecord,
)
from hex_cortex.memory.latent_state_compression import (
    LatentStateJsonlStore,
    LatentStateRecord,
)
from hex_cortex.memory.planner_decision_packet import (
    build_latest_planner_decision_packet,
    summarize_planner_decision_packets,
)
from hex_cortex.memory.skill_registry_integration import (
    SkillRegistryMatchJsonlStore,
    SkillRegistryMatchRecord,
)


def test_planner_decision_packet_blocks_missing_match(tmp_path) -> None:
    payload = build_latest_planner_decision_packet(tmp_path / "profile")
    record = payload["packet_record"]

    assert record["planner_decision"] == "planner_blocked"
    assert record["next_action"] == "build_skill_registry_match"
    assert record["action_allowed"] is False


def test_planner_decision_packet_watches_fallback_match(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_sources(profile, registry_status="fallback", match_score=0.4125)

    payload = build_latest_planner_decision_packet(profile)
    record = payload["packet_record"]

    assert record["planner_decision"] == "planner_watch"
    assert record["next_action"] == "register_or_activate_skill"
    assert record["action_allowed"] is False


def test_planner_decision_packet_allows_matched_skill(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_sources(profile, registry_status="matched", match_score=0.82)

    payload = build_latest_planner_decision_packet(profile)
    summary = summarize_planner_decision_packets(
        profile / "planner-decision-packet.jsonl"
    )
    record = payload["packet_record"]

    assert record["planner_decision"] == "planner_ready"
    assert record["action_allowed"] is True
    assert record["overall_confidence"] > 0.8
    assert summary["latest_planner_decision"] == "planner_ready"


def _write_sources(profile, *, registry_status: str, match_score: float) -> None:
    LatentStateJsonlStore(profile / "latent-state.jsonl").append(
        LatentStateRecord(
            profile_path=str(profile),
            source_candidate_id="world_a",
            source_score_id="skill_score_a",
            source_cost_id="action_cost_a",
            tokens=["state:watch", "skill:operator_watch_review"],
            vector=[0.6, 0.8, 1.0, 0.825, 0.825, 1.0, 1.0, 1.0],
            vector_dim=8,
            compression_score=0.8812,
            suggested_skill="operator_watch_review",
            candidate_action="review_watch_reasons",
            action_score=0.825,
            verdict="latent_state_valid",
            reasons=["latent_state_compressed"],
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
    SkillRegistryMatchJsonlStore(profile / "skill-registry-match.jsonl").append(
        SkillRegistryMatchRecord(
            profile_path=str(profile),
            latent_id="latent_a",
            registry_path=str(profile / "skills.jsonl"),
            registry_status=registry_status,
            latent_suggested_skill="operator_watch_review",
            matched_skill_id="skill_a" if registry_status == "matched" else None,
            matched_skill_name="operator_watch_review",
            matched_skill_confidence=1.0 if registry_status == "matched" else None,
            match_score=match_score,
            match_reason="test_match",
            trigger_tags=["operator_watch_review", "watch"],
            action_score=0.825,
            compression_score=0.8812,
        )
    )
