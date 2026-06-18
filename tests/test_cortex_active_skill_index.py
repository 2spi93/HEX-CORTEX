from hex_cortex.memory.cortex_active_skill_index import (
    CORTEX_ACTIVE_SKILL_INDEX_FILENAME,
    build_cortex_active_skill_index,
    summarize_cortex_active_skill_indexes,
)
from hex_cortex.memory.cortex_skill_activation_apply import (
    CORTEX_SKILL_ACTIVATION_APPLY_FILENAME,
    CortexSkillActivationApplyJsonlStore,
    CortexSkillActivationApplyRecord,
)


def _apply(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "skill_key": "architecture:e192e479ed25",
        "domain": "architecture",
        "source_manual_id": "manual_1",
        "source_manual_hash": "a" * 64,
        "source_gate_hash": "b" * 64,
        "source_library_hash": "c" * 64,
        "source_candidate_hash": "d" * 64,
        "source_learning_ids": ["learning_1"],
        "source_learning_hashes": ["e" * 64],
        "reusable_rule": "Before adding routers or executors, check whether better learning memory is needed.",
        "evidence_count": 1,
        "average_confidence": 0.95,
        "apply_status": "applied",
        "apply_decision": "skill_activation_applied",
        "apply_allowed": True,
        "effective_active": True,
        "activation_source": "manual_operator_choice",
        "next_action": "skill_available_for_controlled_use",
        "blockers": [],
        "apply_hash": "f" * 64,
        "reasons": ["manual_activation_accepted"],
    }
    payload.update(overrides)
    record = CortexSkillActivationApplyRecord(**payload)
    current_path = profile / CORTEX_SKILL_ACTIVATION_APPLY_FILENAME
    current = CortexSkillActivationApplyJsonlStore(current_path).load()
    CortexSkillActivationApplyJsonlStore(current_path).save([*current, record])
    return record


def test_cortex_active_skill_index_builds_from_effective_active_apply(tmp_path) -> None:
    profile = tmp_path / "profile"
    apply = _apply(profile)

    record = build_cortex_active_skill_index(profile)["index_record"]

    assert record["index_allowed"] is True
    assert record["index_status"] == "ready"
    assert record["index_decision"] == "active_skill_index_ready"
    assert record["active_skill_count"] == 1
    assert record["active_domains"] == ["architecture"]
    assert record["active_skill_keys"] == ["architecture:e192e479ed25"]
    assert record["entries"][0]["source_apply_id"] == apply.apply_id
    assert record["next_action"] == "await_controlled_skill_use"
    assert len(record["index_hash"]) == 64


def test_cortex_active_skill_index_blocks_when_no_active_skills(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = build_cortex_active_skill_index(profile)["index_record"]

    assert record["index_allowed"] is False
    assert record["index_status"] == "empty"
    assert record["active_skill_count"] == 0
    assert "no_effective_active_skills" in record["blockers"]


def test_cortex_active_skill_index_uses_latest_active_apply_by_skill_key(tmp_path) -> None:
    profile = tmp_path / "profile"
    _apply(profile, apply_hash="1" * 64, source_manual_id="manual_old")
    latest = _apply(profile, apply_hash="2" * 64, source_manual_id="manual_new")

    record = build_cortex_active_skill_index(profile)["index_record"]

    assert record["active_skill_count"] == 1
    assert record["entries"][0]["source_apply_id"] == latest.apply_id
    assert record["entries"][0]["source_apply_hash"] == latest.apply_hash


def test_cortex_active_skill_index_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _apply(profile)
    build_cortex_active_skill_index(profile)

    summary = summarize_cortex_active_skill_indexes(profile / CORTEX_ACTIVE_SKILL_INDEX_FILENAME)

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_active_skill_index"
    assert summary["total_index_count"] == 1
    assert summary["latest_index_allowed"] is True
    assert summary["latest_active_skill_count"] == 1
    assert summary["latest_active_skill_keys"] == ["architecture:e192e479ed25"]
    assert summary["latest_next_action"] == "await_controlled_skill_use"
