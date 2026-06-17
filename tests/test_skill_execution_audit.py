from hex_cortex.memory.controlled_skill_gate import (
    ControlledSkillGateJsonlStore,
    ControlledSkillGateRecord,
)
from hex_cortex.memory.skill_execution_audit import (
    build_skill_execution_audit,
    summarize_skill_execution_audits,
)


def test_skill_execution_audit_blocks_missing_gate(tmp_path) -> None:
    payload = build_skill_execution_audit(tmp_path / "profile")
    record = payload["audit_record"]

    assert record["audit_decision"] == "audit_blocked"
    assert record["execution_allowed"] is False
    assert record["next_action"] == "evaluate_controlled_skill_gate"


def test_skill_execution_audit_watches_gate_watch(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_gate(profile, status="watch", decision="gate_watch", allowed=False)

    payload = build_skill_execution_audit(profile)
    record = payload["audit_record"]

    assert record["audit_decision"] == "audit_watch"
    assert record["execution_allowed"] is False
    assert record["next_action"] == "register_or_activate_skill"


def test_skill_execution_audit_allows_ready_audit(tmp_path) -> None:
    profile = tmp_path / "profile"
    _write_gate(profile, status="ready", decision="gate_ready", allowed=True)

    payload = build_skill_execution_audit(profile)
    summary = summarize_skill_execution_audits(
        profile / "skill-execution-audit.jsonl"
    )
    record = payload["audit_record"]

    assert record["audit_decision"] == "audit_ready"
    assert record["execution_allowed"] is True
    assert record["next_action"] == "create_skill_execution_receipt"
    assert summary["latest_audit_decision"] == "audit_ready"


def _write_gate(profile, *, status: str, decision: str, allowed: bool) -> None:
    ControlledSkillGateJsonlStore(profile / "controlled-skill-gate.jsonl").append(
        ControlledSkillGateRecord(
            profile_path=str(profile),
            source_packet_id="planner_a",
            source_replay_id="replay_a",
            selected_skill="operator_watch_review",
            selected_action="review_watch_reasons",
            gate_status=status,
            gate_decision=decision,
            execution_allowed=allowed,
            execution_mode="controlled_staging_only" if allowed else "none",
            next_action=(
                "stage_controlled_skill_execution_audit"
                if allowed
                else "register_or_activate_skill"
            ),
            planner_decision="planner_ready" if allowed else "planner_watch",
            replay_recommendation=(
                "stage_controlled_skill_execution_gate"
                if allowed
                else "register_or_activate_missing_skills"
            ),
            gate_confidence=0.8421 if allowed else 0.7062,
            reasons=["test_gate"],
        )
    )
