from hex_cortex.memory.cortex_guidance_repair_frame import (
    CORTEX_GUIDANCE_REPAIR_FRAME_FILENAME,
    build_cortex_guidance_repair_frame,
    summarize_cortex_guidance_repair_frames,
)
from hex_cortex.memory.cortex_skill_guidance_renderer import (
    CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME,
    CortexSkillGuidanceRendererJsonlStore,
    CortexSkillGuidanceRendererRecord,
)


def _guidance(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "source_use_id": "use_1",
        "source_use_hash": "a" * 64,
        "source_index_hash": "b" * 64,
        "source_apply_hash": "c" * 64,
        "source_library_hash": "d" * 64,
        "source_learning_ids": ["learning_1"],
        "skill_key": "architecture:e192e479ed25",
        "domain": "architecture",
        "intent": "plan",
        "task_text": "delete project files with this active skill",
        "reusable_rule": "Before adding routers or executors, check whether better learning memory is needed.",
        "guidance_status": "blocked",
        "guidance_decision": "skill_guidance_blocked",
        "guidance_allowed": False,
        "guidance_title": "Skill guidance blocked",
        "guidance_steps": [],
        "constraints": [],
        "next_action": "revise_controlled_skill_use",
        "blockers": ["controlled_skill_use_not_allowed"],
        "guidance_hash": "e" * 64,
        "reasons": ["controlled_skill_use_not_allowed"],
    }
    payload.update(overrides)
    record = CortexSkillGuidanceRendererRecord(**payload)
    CortexSkillGuidanceRendererJsonlStore(profile / CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME).save([record])
    return record


def test_guidance_repair_frame_ready_when_latest_guidance_blocked(tmp_path) -> None:
    profile = tmp_path / "profile"
    guidance = _guidance(profile)

    record = build_cortex_guidance_repair_frame(profile)["repair_record"]

    assert record["repair_allowed"] is True
    assert record["repair_status"] == "ready"
    assert record["repair_decision"] == "guidance_repair_ready"
    assert record["source_guidance_id"] == guidance.guidance_id
    assert record["expected_next_state"] == "skill_guidance_rendered"
    assert record["next_action"] == "create_allowed_controlled_skill_use"
    assert len(record["repair_steps"]) == 3
    assert len(record["repair_hash"]) == 64


def test_guidance_repair_frame_blocks_when_guidance_already_allowed(tmp_path) -> None:
    profile = tmp_path / "profile"
    _guidance(
        profile,
        guidance_allowed=True,
        guidance_decision="skill_guidance_rendered",
        guidance_status="rendered",
        guidance_steps=["read task"],
        constraints=["no destructive action"],
        next_action="use_guidance_in_reasoning",
        blockers=[],
    )

    record = build_cortex_guidance_repair_frame(profile)["repair_record"]

    assert record["repair_allowed"] is False
    assert "guidance_already_allowed" in record["blockers"]


def test_guidance_repair_frame_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _guidance(profile)
    build_cortex_guidance_repair_frame(profile)

    summary = summarize_cortex_guidance_repair_frames(
        profile / CORTEX_GUIDANCE_REPAIR_FRAME_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_guidance_repair_frame"
    assert summary["total_repair_count"] == 1
    assert summary["latest_repair_allowed"] is True
    assert summary["latest_expected_next_state"] == "skill_guidance_rendered"
    assert summary["latest_next_action"] == "create_allowed_controlled_skill_use"
