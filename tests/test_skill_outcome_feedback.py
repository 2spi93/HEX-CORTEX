from hex_cortex.memory.skill_execution_audit import (
    SkillExecutionAuditJsonlStore,
    SkillExecutionAuditRecord,
)
from hex_cortex.memory.skill_outcome_feedback import (
    record_skill_outcome_feedback,
    summarize_skill_outcome_feedback,
)


def test_skill_outcome_feedback_blocks_missing_audit(tmp_path) -> None:
    payload = record_skill_outcome_feedback(tmp_path / "profile")
    record = payload["feedback_record"]

    assert record["feedback_decision"] == "feedback_blocked"
    assert record["next_action"] == "build_skill_execution_audit"


def test_skill_outcome_feedback_watches_non_execution_audit(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_audit(profile, allowed=False)

    payload = record_skill_outcome_feedback(profile)
    record = payload["feedback_record"]

    assert record["feedback_decision"] == "feedback_watch"
    assert record["observed_outcome"] == "not_observed"
    assert record["next_action"] == "register_or_activate_skill"


def test_skill_outcome_feedback_scores_success(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_audit(profile, allowed=True)

    payload = record_skill_outcome_feedback(profile, observed_outcome="success")
    summary = summarize_skill_outcome_feedback(
        profile / "skill-outcome-feedback.jsonl"
    )
    record = payload["feedback_record"]

    assert record["feedback_decision"] == "feedback_success"
    assert record["outcome_score"] == 1.0
    assert summary["latest_feedback_decision"] == "feedback_success"


def test_skill_outcome_feedback_blocks_failure(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_audit(profile, allowed=True)

    payload = record_skill_outcome_feedback(profile, observed_outcome="failure")
    record = payload["feedback_record"]

    assert record["feedback_decision"] == "feedback_blocked"
    assert record["next_action"] == "repair_skill_or_gate"


def _write_audit(profile, *, allowed: bool) -> None:
    SkillExecutionAuditJsonlStore(profile / "skill-execution-audit.jsonl").append(
        SkillExecutionAuditRecord(
            profile_path=str(profile),
            source_gate_id="gate_a",
            selected_skill="operator_watch_review",
            selected_action="review_watch_reasons",
            audit_status="ready" if allowed else "watch",
            audit_decision="audit_ready" if allowed else "audit_watch",
            execution_allowed=allowed,
            execution_mode="controlled_staging_only" if allowed else "none",
            audit_stage="controlled_staging_audit" if allowed else "pre_execution",
            next_action=(
                "create_skill_execution_receipt"
                if allowed
                else "register_or_activate_skill"
            ),
            gate_decision="gate_ready" if allowed else "gate_watch",
            gate_confidence=0.8421 if allowed else 0.7062,
            reasons=["test_audit"],
        )
    )
