from hex_cortex.memory.cortex_guided_reasoning_frame import (
    CORTEX_GUIDED_REASONING_FRAME_FILENAME,
    build_cortex_guided_reasoning_frame,
    summarize_cortex_guided_reasoning_frames,
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
        "intent": "inspect",
        "task_text": "inspect whether this architecture rule should guide the next build step",
        "reusable_rule": "Before adding routers or executors, check whether better learning memory is needed.",
        "guidance_status": "rendered",
        "guidance_decision": "skill_guidance_rendered",
        "guidance_allowed": True,
        "guidance_title": "Guidance for architecture:e192e479ed25",
        "guidance_steps": ["read task", "apply rule"],
        "constraints": ["no destructive action", "keep lineage"],
        "next_action": "use_guidance_in_reasoning",
        "blockers": [],
        "guidance_hash": "e" * 64,
        "reasons": ["controlled_skill_use_allowed"],
    }
    payload.update(overrides)
    record = CortexSkillGuidanceRendererRecord(**payload)
    CortexSkillGuidanceRendererJsonlStore(profile / CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME).save([record])
    return record


def test_guided_reasoning_frame_builds_from_allowed_guidance(tmp_path) -> None:
    profile = tmp_path / "profile"
    guidance = _guidance(profile)

    record = build_cortex_guided_reasoning_frame(profile)["frame_records"][0]

    assert record["frame_allowed"] is True
    assert record["frame_status"] == "ready"
    assert record["frame_decision"] == "guided_reasoning_frame_ready"
    assert record["source_guidance_id"] == guidance.guidance_id
    assert record["skill_key"] == "architecture:e192e479ed25"
    assert record["next_action"] == "choose_next_build_step_with_guidance"
    assert len(record["blocked_directions"]) == 3
    assert len(record["frame_hash"]) == 64


def test_guided_reasoning_frame_blocks_from_blocked_guidance(tmp_path) -> None:
    profile = tmp_path / "profile"
    _guidance(
        profile,
        guidance_allowed=False,
        guidance_decision="skill_guidance_blocked",
        guidance_status="blocked",
        guidance_steps=[],
        constraints=[],
        next_action="revise_controlled_skill_use",
        blockers=["controlled_skill_use_not_allowed"],
    )

    record = build_cortex_guided_reasoning_frame(profile)["frame_records"][0]

    assert record["frame_allowed"] is False
    assert "skill_guidance_not_allowed" in record["blockers"]


def test_guided_reasoning_frame_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _guidance(profile)
    build_cortex_guided_reasoning_frame(profile)

    summary = summarize_cortex_guided_reasoning_frames(
        profile / CORTEX_GUIDED_REASONING_FRAME_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_guided_reasoning_frame"
    assert summary["total_frame_count"] == 1
    assert summary["allowed_frame_count"] == 1
    assert summary["latest_frame_allowed"] is True
    assert summary["latest_next_action"] == "choose_next_build_step_with_guidance"
