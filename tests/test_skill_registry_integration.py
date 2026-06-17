from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.memory.latent_state_compression import (
    LatentStateJsonlStore,
    LatentStateRecord,
)
from hex_cortex.memory.skill_registry_integration import (
    match_latest_latent_to_skill_registry,
    summarize_skill_registry_matches,
)


def test_skill_registry_integration_handles_missing_latent(tmp_path) -> None:
    payload = match_latest_latent_to_skill_registry(tmp_path / "profile")
    record = payload["match_record"]

    assert record["registry_status"] == "latent_missing"
    assert record["match_score"] == 0.0


def test_skill_registry_integration_falls_back_without_active_skill(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_latent(profile)

    payload = match_latest_latent_to_skill_registry(profile)
    record = payload["match_record"]

    assert record["registry_status"] == "fallback"
    assert record["matched_skill_name"] == "operator_watch_review"
    assert record["match_reason"] == "no_active_registry_skill_matched"


def test_skill_registry_integration_matches_active_skill(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_latent(profile)
    SkillJsonlStore(profile / "skills.jsonl").append(
        SkillRecord(
            name="operator_watch_review",
            description="Review watch reasons before allowing dispatch.",
            trigger_tags=["operator_watch_review", "review_watch_reasons", "watch"],
            workflow_steps=["inspect_watch_reasons", "confirm_next_action"],
            confidence=1.0,
            status=SkillStatus.ACTIVE,
        )
    )

    payload = match_latest_latent_to_skill_registry(profile)
    summary = summarize_skill_registry_matches(profile / "skill-registry-match.jsonl")
    record = payload["match_record"]

    assert record["registry_status"] == "matched"
    assert record["matched_skill_name"] == "operator_watch_review"
    assert record["match_score"] > 0.7
    assert summary["latest_registry_status"] == "matched"


def _write_latent(profile) -> None:
    LatentStateJsonlStore(profile / "latent-state.jsonl").append(
        LatentStateRecord(
            profile_path=str(profile),
            source_candidate_id="world_a",
            source_score_id="skill_score_a",
            source_cost_id="action_cost_a",
            tokens=[
                "state:watch",
                "action:review_watch_reasons",
                "skill:operator_watch_review",
                "risk:low",
                "cost:low",
                "verdict:action_cost_valid",
            ],
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
