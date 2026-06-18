from hex_cortex.memory.cortex_controlled_skill_use import (
    CORTEX_CONTROLLED_SKILL_USE_FILENAME,
    CortexControlledSkillUseJsonlStore,
    CortexControlledSkillUseRecord,
)
from hex_cortex.memory.cortex_skill_guidance_renderer import (
    CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME,
    render_cortex_skill_guidance,
    summarize_cortex_skill_guidance_renderers,
)


def _use(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "requested_skill_key": None,
        "requested_domain": "architecture",
        "intent": "inspect",
        "task_text": "inspect whether this architecture rule should guide the next build step",
        "selected_skill_key": "architecture:e192e479ed25",
        "selected_domain": "architecture",
        "selected_reusable_rule": "Before adding routers or executors, check whether the system needs better learning memory.",
        "source_index_id": "index_1",
        "source_index_hash": "a" * 64,
        "source_apply_hash": "b" * 64,
        "source_library_hash": "c" * 64,
        "source_learning_ids": ["learning_1"],
        "use_status": "allowed",
        "use_decision": "controlled_skill_use_allowed",
        "use_allowed": True,
        "next_action": "render_controlled_skill_guidance",
        "blockers": [],
        "use_hash": "d" * 64,
        "reasons": ["active_skill_selected"],
    }
    payload.update(overrides)
    record = CortexControlledSkillUseRecord(**payload)
    CortexControlledSkillUseJsonlStore(profile / CORTEX_CONTROLLED_SKILL_USE_FILENAME).save([record])
    return record


def test_skill_guidance_renderer_renders_allowed_controlled_use(tmp_path) -> None:
    profile = tmp_path / "profile"
    use = _use(profile)

    payload = render_cortex_skill_guidance(profile)
    record = payload["guidance_records"][0]

    assert record["guidance_allowed"] is True
    assert record["guidance_status"] == "rendered"
    assert record["guidance_decision"] == "skill_guidance_rendered"
    assert record["skill_key"] == "architecture:e192e479ed25"
    assert record["source_use_id"] == use.use_id
    assert record["next_action"] == "use_guidance_in_reasoning"
    assert len(record["guidance_steps"]) == 4
    assert len(record["constraints"]) == 4
    assert len(record["guidance_hash"]) == 64


def test_skill_guidance_renderer_blocks_disallowed_controlled_use(tmp_path) -> None:
    profile = tmp_path / "profile"
    _use(
        profile,
        use_status="blocked",
        use_decision="controlled_skill_use_blocked",
        use_allowed=False,
        next_action="revise_controlled_skill_use",
        blockers=["task_contains_blocked_action"],
    )

    record = render_cortex_skill_guidance(profile)["guidance_records"][0]

    assert record["guidance_allowed"] is False
    assert "controlled_skill_use_not_allowed" in record["blockers"]


def test_skill_guidance_renderer_is_idempotent_by_use_hash(tmp_path) -> None:
    profile = tmp_path / "profile"
    _use(profile)

    first = render_cortex_skill_guidance(profile)
    second = render_cortex_skill_guidance(profile)

    assert len(first["guidance_records"]) == 1
    assert second["guidance_records"] == []
    assert second["guidance_count"] == 1


def test_skill_guidance_renderer_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _use(profile)
    render_cortex_skill_guidance(profile)

    summary = summarize_cortex_skill_guidance_renderers(
        profile / CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_skill_guidance_renderer"
    assert summary["total_guidance_count"] == 1
    assert summary["allowed_guidance_count"] == 1
    assert summary["latest_guidance_allowed"] is True
    assert summary["latest_guidance_decision"] == "skill_guidance_rendered"
    assert summary["latest_next_action"] == "use_guidance_in_reasoning"
