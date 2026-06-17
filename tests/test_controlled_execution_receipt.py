from hex_cortex.memory.controlled_execution_receipt import (
    build_controlled_execution_receipt,
    summarize_controlled_execution_receipts,
)
from hex_cortex.memory.skill_execution_audit import (
    SkillExecutionAuditJsonlStore,
    SkillExecutionAuditRecord,
)
from hex_cortex.memory.skill_outcome_feedback import (
    SkillOutcomeFeedbackJsonlStore,
    SkillOutcomeFeedbackRecord,
)


def test_controlled_execution_receipt_blocks_missing_audit(tmp_path) -> None:
    payload = build_controlled_execution_receipt(tmp_path / "profile")
    record = payload["receipt_record"]

    assert record["receipt_decision"] == "receipt_blocked"
    assert record["execution_allowed"] is False
    assert record["certification"] == "execution_not_certified"


def test_controlled_execution_receipt_certifies_not_executed(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_audit(profile, allowed=False)
    _write_feedback(profile, outcome="not_observed", allowed=False)

    payload = build_controlled_execution_receipt(profile)
    record = payload["receipt_record"]

    assert record["receipt_decision"] == "receipt_not_executed"
    assert record["execution_observed"] is False
    assert record["certification"] == "execution_prevented_by_audit"


def test_controlled_execution_receipt_certifies_success(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_audit(profile, allowed=True)
    _write_feedback(profile, outcome="success", allowed=True)

    payload = build_controlled_execution_receipt(profile)
    summary = summarize_controlled_execution_receipts(
        profile / "controlled-execution-receipt.jsonl"
    )
    record = payload["receipt_record"]

    assert record["receipt_decision"] == "receipt_success"
    assert record["execution_observed"] is True
    assert record["certification"] == "controlled_execution_success_observed"
    assert summary["latest_receipt_decision"] == "receipt_success"


def test_controlled_execution_receipt_certifies_failure(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_audit(profile, allowed=True)
    _write_feedback(profile, outcome="failure", allowed=True)

    payload = build_controlled_execution_receipt(profile)
    record = payload["receipt_record"]

    assert record["receipt_decision"] == "receipt_failure"
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


def _write_feedback(profile, *, outcome: str, allowed: bool) -> None:
    SkillOutcomeFeedbackJsonlStore(profile / "skill-outcome-feedback.jsonl").append(
        SkillOutcomeFeedbackRecord(
            profile_path=str(profile),
            source_audit_id="audit_a",
            selected_skill="operator_watch_review",
            selected_action="review_watch_reasons",
            audit_decision="audit_ready" if allowed else "audit_watch",
            execution_allowed=allowed,
            observed_outcome=outcome,
            outcome_score=1.0 if outcome == "success" else 0.7,
            feedback_status="ready" if outcome == "success" else "watch",
            feedback_decision=(
                "feedback_success" if outcome == "success" else "feedback_watch"
            ),
            next_action=(
                "promote_skill_confidence_candidate"
                if outcome == "success"
                else "register_or_activate_skill"
            ),
            reasons=["test_feedback"],
        )
    )
