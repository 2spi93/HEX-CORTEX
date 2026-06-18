from hex_cortex.memory.cortex_guided_reasoning_frame import (
    CORTEX_GUIDED_REASONING_FRAME_FILENAME,
    CortexGuidedReasoningFrameJsonlStore,
    CortexGuidedReasoningFrameRecord,
)
from hex_cortex.memory.cortex_next_build_decision import (
    CORTEX_NEXT_BUILD_DECISION_FILENAME,
    build_cortex_next_build_decision,
    summarize_cortex_next_build_decisions,
)


def _frame(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "source_guidance_id": "guidance_1",
        "source_guidance_hash": "a" * 64,
        "source_use_hash": "b" * 64,
        "source_index_hash": "c" * 64,
        "source_apply_hash": "d" * 64,
        "source_library_hash": "e" * 64,
        "source_learning_ids": ["learning_1"],
        "skill_key": "architecture:e192e479ed25",
        "domain": "architecture",
        "intent": "inspect",
        "question": "inspect whether this architecture rule should guide the next build step",
        "applicable_rule": "Before adding routers or executors, check whether better learning memory is needed.",
        "constraints": ["No destructive action is authorized."],
        "recommended_direction": "Use the active rule to prefer learning, memory, evidence, and alignment improvements before adding routers, executors, or irreversible behavior.",
        "blocked_directions": ["Do not execute or mutate state from the reasoning frame."],
        "frame_status": "ready",
        "frame_decision": "guided_reasoning_frame_ready",
        "frame_allowed": True,
        "next_action": "choose_next_build_step_with_guidance",
        "blockers": [],
        "frame_hash": "f" * 64,
        "reasons": ["guidance_allowed"],
    }
    payload.update(overrides)
    record = CortexGuidedReasoningFrameRecord(**payload)
    CortexGuidedReasoningFrameJsonlStore(profile / CORTEX_GUIDED_REASONING_FRAME_FILENAME).save([record])
    return record


def test_next_build_decision_prefers_learning_memory_from_frame(tmp_path) -> None:
    profile = tmp_path / "profile"
    frame = _frame(profile)

    record = build_cortex_next_build_decision(profile)["decision_records"][0]

    assert record["decision_allowed"] is True
    assert record["decision_status"] == "ready"
    assert record["decision_result"] == "next_build_decision_ready"
    assert record["chosen_build_direction"] == "continue_learning_memory"
    assert record["next_action"] == "build_memory_retrieval_selector"
    assert record["source_frame_id"] == frame.frame_id
    assert len(record["decision_hash"]) == 64


def test_next_build_decision_blocks_from_blocked_frame(tmp_path) -> None:
    profile = tmp_path / "profile"
    _frame(
        profile,
        frame_allowed=False,
        frame_decision="guided_reasoning_frame_blocked",
        frame_status="blocked",
        next_action="repair_skill_guidance",
        blockers=["skill_guidance_not_allowed"],
    )

    record = build_cortex_next_build_decision(profile)["decision_records"][0]

    assert record["decision_allowed"] is False
    assert record["chosen_build_direction"] == "repair"
    assert "guided_reasoning_frame_not_allowed" in record["blockers"]


def test_next_build_decision_is_idempotent_by_frame_hash(tmp_path) -> None:
    profile = tmp_path / "profile"
    _frame(profile)

    first = build_cortex_next_build_decision(profile)
    second = build_cortex_next_build_decision(profile)

    assert len(first["decision_records"]) == 1
    assert second["decision_records"] == []
    assert second["decision_count"] == 1


def test_next_build_decision_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _frame(profile)
    build_cortex_next_build_decision(profile)

    summary = summarize_cortex_next_build_decisions(
        profile / CORTEX_NEXT_BUILD_DECISION_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_next_build_decision"
    assert summary["total_decision_count"] == 1
    assert summary["allowed_decision_count"] == 1
    assert summary["latest_decision_allowed"] is True
    assert summary["latest_chosen_build_direction"] == "continue_learning_memory"
    assert summary["latest_next_action"] == "build_memory_retrieval_selector"
