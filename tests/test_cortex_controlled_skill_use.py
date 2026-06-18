from hex_cortex.memory.cortex_active_skill_index import (
    CORTEX_ACTIVE_SKILL_INDEX_FILENAME,
    CortexActiveSkillIndexEntry,
    CortexActiveSkillIndexJsonlStore,
    CortexActiveSkillIndexRecord,
)
from hex_cortex.memory.cortex_controlled_skill_use import (
    CORTEX_CONTROLLED_SKILL_USE_FILENAME,
    record_cortex_controlled_skill_use,
    summarize_cortex_controlled_skill_uses,
)


def _index(profile, *, entries=None, **overrides):
    entry = CortexActiveSkillIndexEntry(
        skill_key="architecture:e192e479ed25",
        domain="architecture",
        reusable_rule="Before adding routers or executors, check whether better learning memory is needed.",
        source_apply_id="apply_1",
        source_apply_hash="a" * 64,
        source_library_hash="b" * 64,
        source_manual_hash="c" * 64,
        source_learning_ids=["learning_1"],
        evidence_count=1,
        average_confidence=0.95,
    )
    active_entries = entries if entries is not None else [entry]
    payload = {
        "profile_path": str(profile),
        "index_status": "ready",
        "index_decision": "active_skill_index_ready",
        "index_allowed": True,
        "active_skill_count": len(active_entries),
        "active_domains": sorted({item.domain for item in active_entries}),
        "active_skill_keys": [item.skill_key for item in active_entries],
        "entries": active_entries,
        "next_action": "await_controlled_skill_use",
        "blockers": [],
        "index_hash": "d" * 64,
        "reasons": ["effective_active_skills_indexed"],
    }
    payload.update(overrides)
    record = CortexActiveSkillIndexRecord(**payload)
    CortexActiveSkillIndexJsonlStore(profile / CORTEX_ACTIVE_SKILL_INDEX_FILENAME).save([record])
    return record


def test_controlled_skill_use_allows_inspect_by_domain(tmp_path) -> None:
    profile = tmp_path / "profile"
    _index(profile)

    record = record_cortex_controlled_skill_use(
        profile,
        intent="inspect",
        task_text="inspect whether this architecture rule should guide the next build step",
        domain="architecture",
    )["use_record"]

    assert record["use_allowed"] is True
    assert record["use_decision"] == "controlled_skill_use_allowed"
    assert record["selected_skill_key"] == "architecture:e192e479ed25"
    assert record["next_action"] == "render_controlled_skill_guidance"
    assert len(record["use_hash"]) == 64


def test_controlled_skill_use_blocks_destructive_task_text(tmp_path) -> None:
    profile = tmp_path / "profile"
    _index(profile)

    record = record_cortex_controlled_skill_use(
        profile,
        intent="plan",
        task_text="delete project files with this active skill",
        domain="architecture",
    )["use_record"]

    assert record["use_allowed"] is False
    assert "task_contains_blocked_action" in record["blockers"]


def test_controlled_skill_use_blocks_unknown_skill_key(tmp_path) -> None:
    profile = tmp_path / "profile"
    _index(profile)

    record = record_cortex_controlled_skill_use(
        profile,
        intent="inspect",
        task_text="inspect whether a missing skill exists",
        skill_key="architecture:missing",
    )["use_record"]

    assert record["use_allowed"] is False
    assert "no_matching_active_skill" in record["blockers"]


def test_controlled_skill_use_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _index(profile)
    record_cortex_controlled_skill_use(
        profile,
        intent="apply_rule",
        task_text="apply this rule as guidance for choosing the next memory build step",
        domain="architecture",
    )

    summary = summarize_cortex_controlled_skill_uses(
        profile / CORTEX_CONTROLLED_SKILL_USE_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_controlled_skill_use"
    assert summary["total_use_count"] == 1
    assert summary["allowed_use_count"] == 1
    assert summary["latest_intent"] == "apply_rule"
    assert summary["latest_selected_domain"] == "architecture"
    assert summary["latest_use_allowed"] is True
