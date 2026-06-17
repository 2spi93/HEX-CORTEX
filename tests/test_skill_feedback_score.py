from hex_cortex.memory.registry_learning_candidate import (
    RegistryLearningCandidateJsonlStore,
    RegistryLearningCandidateRecord,
)
from hex_cortex.memory.skill_feedback_score import (
    build_skill_feedback_score,
    summarize_skill_feedback_scores,
)
from hex_cortex.memory.skill_outcome_feedback import (
    SkillOutcomeFeedbackJsonlStore,
    SkillOutcomeFeedbackRecord,
)


def test_skill_feedback_score_blocks_missing_feedback(tmp_path) -> None:
    payload = build_skill_feedback_score(tmp_path / "profile")
    record = payload["score_record"]

    assert record["score_decision"] == "score_blocked"
    assert record["final_score"] == 0.0


def test_skill_feedback_score_holds_not_observed(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_learning(profile, score=0.0)
    _write_feedback(profile, outcome="not_observed")

    payload = build_skill_feedback_score(profile)
    record = payload["score_record"]

    assert record["score_decision"] == "score_hold"
    assert record["final_score"] == 0.0
    assert record["next_action"] == "register_or_activate_skill"


def test_skill_feedback_score_readies_success(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_learning(profile, score=1.0)
    _write_feedback(profile, outcome="success")

    payload = build_skill_feedback_score(profile)
    summary = summarize_skill_feedback_scores(profile / "skill-feedback-score.jsonl")
    record = payload["score_record"]

    assert record["score_decision"] == "score_ready"
    assert record["final_score"] == 1.0
    assert summary["latest_score_decision"] == "score_ready"


def _write_learning(profile, *, score: float) -> None:
    RegistryLearningCandidateJsonlStore(
        profile / "registry-learning-candidate.jsonl"
    ).append(
        RegistryLearningCandidateRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_feedback_id="feedback_a",
            source_match_id="match_a",
            registry_status="fallback",
            observed_outcome="success" if score else "not_observed",
            success_count=1 if score else 0,
            failure_count=0,
            blocked_count=0,
            not_observed_count=0 if score else 1,
            learning_score=score,
            learning_status="ready" if score else "watch",
            learning_decision="learning_ready" if score else "learning_hold",
            next_action=(
                "prepare_operator_review" if score else "register_or_activate_skill"
            ),
            reasons=["test_learning"],
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
            feedback_decision=(
                "feedback_success" if outcome == "success" else "feedback_watch"
            ),
            next_action=(
                "prepare_operator_review"
                if outcome == "success"
                else "register_or_activate_skill"
            ),
            reasons=["test_feedback"],
        )
    )
