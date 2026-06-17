from hex_cortex.memory.registry_learning_candidate import (
    build_registry_learning_candidate,
    summarize_registry_learning_candidates,
)
from hex_cortex.memory.skill_outcome_feedback import (
    SkillOutcomeFeedbackJsonlStore,
    SkillOutcomeFeedbackRecord,
)
from hex_cortex.memory.skill_registry_integration import (
    SkillRegistryMatchJsonlStore,
    SkillRegistryMatchRecord,
)


def test_registry_learning_candidate_blocks_missing_feedback(tmp_path) -> None:
    payload = build_registry_learning_candidate(tmp_path / "profile")
    record = payload["learning_record"]

    assert record["learning_decision"] == "learning_blocked"
    assert record["next_action"] == "record_skill_outcome_feedback"


def test_registry_learning_candidate_holds_not_observed_feedback(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_match(profile, registry_status="fallback")
    _write_feedback(profile, outcome="not_observed")

    payload = build_registry_learning_candidate(profile)
    record = payload["learning_record"]

    assert record["learning_decision"] == "learning_hold"
    assert record["next_action"] == "register_or_activate_skill"


def test_registry_learning_candidate_readies_successful_fallback(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_match(profile, registry_status="fallback")
    _write_feedback(profile, outcome="success")

    payload = build_registry_learning_candidate(profile)
    summary = summarize_registry_learning_candidates(
        profile / "registry-learning-candidate.jsonl"
    )
    record = payload["learning_record"]

    assert record["learning_decision"] == "learning_ready"
    assert record["learning_score"] == 1.0
    assert record["next_action"] == "prepare_skill_registry_update_proposal"
    assert summary["latest_learning_decision"] == "learning_ready"


def _write_match(profile, *, registry_status: str) -> None:
    SkillRegistryMatchJsonlStore(profile / "skill-registry-match.jsonl").append(
        SkillRegistryMatchRecord(
            profile_path=str(profile),
            latent_id="latent_a",
            registry_path=str(profile / "skills.jsonl"),
            registry_status=registry_status,
            latent_suggested_skill="operator_watch_review",
            matched_skill_id=None,
            matched_skill_name="operator_watch_review",
            matched_skill_confidence=None,
            match_score=0.4125,
            match_reason="test_match",
            trigger_tags=["operator_watch_review", "watch"],
            action_score=0.825,
            compression_score=0.8812,
        )
    )


def _write_feedback(profile, *, outcome: str) -> None:
    SkillOutcomeFeedbackJsonlStore(profile / "skill-outcome-feedback.jsonl").append(
        SkillOutcomeFeedbackRecord(
            profile_path=str(profile),
            source_audit_id="audit_a",
            selected_skill="operator_watch_review",
            selected_action="review_watch_reasons",
            audit_decision="audit_ready" if outcome == "success" else "audit_watch",
            execution_allowed=outcome == "success",
            observed_outcome=outcome,
            outcome_score=1.0 if outcome == "success" else 0.7,
            feedback_status="ready" if outcome == "success" else "watch",
            feedback_decision="feedback_success" if outcome == "success" else "feedback_watch",
            next_action=(
                "promote_skill_confidence_candidate"
                if outcome == "success"
                else "register_or_activate_skill"
            ),
            reasons=["test_feedback"],
        )
    )
