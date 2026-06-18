from hex_cortex.memory.cortex_manual_skill_activation import (
    CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME,
    CortexManualSkillActivationJsonlStore,
    CortexManualSkillActivationRecord,
)
from hex_cortex.memory.cortex_skill_activation_apply import (
    CORTEX_SKILL_ACTIVATION_APPLY_FILENAME,
    build_cortex_skill_activation_apply,
    summarize_cortex_skill_activation_applies,
)
from hex_cortex.memory.cortex_skill_library import (
    CORTEX_SKILL_LIBRARY_FILENAME,
    CortexSkillLibraryJsonlStore,
    CortexSkillLibraryRecord,
)


def _library(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "skill_key": "architecture:e192e479ed25",
        "domain": "architecture",
        "reusable_rule": "Before adding routers or executors, check whether better learning memory is needed.",
        "source_candidate_id": "candidate_1",
        "source_candidate_hash": "a" * 64,
        "source_learning_ids": ["learning_1"],
        "source_learning_hashes": ["b" * 64],
        "evidence_count": 1,
        "average_confidence": 0.95,
        "library_status": "registered",
        "library_decision": "skill_library_registered",
        "library_allowed": True,
        "active": False,
        "activation_status": "inactive_pending_gate",
        "next_action": "await_skill_activation_gate",
        "blockers": [],
        "library_hash": "c" * 64,
        "reasons": ["skill_candidate_promotable"],
    }
    payload.update(overrides)
    record = CortexSkillLibraryRecord(**payload)
    CortexSkillLibraryJsonlStore(profile / CORTEX_SKILL_LIBRARY_FILENAME).save([record])
    return record


def _manual(profile, library, **overrides):
    payload = {
        "profile_path": str(profile),
        "skill_key": library.skill_key,
        "domain": library.domain,
        "operator_choice": "activate",
        "operator_note": "operator explicitly approved this skill for the next apply stage",
        "source_gate_id": "gate_1",
        "source_gate_hash": "d" * 64,
        "source_library_hash": library.library_hash,
        "source_candidate_hash": library.source_candidate_hash,
        "source_learning_ids": library.source_learning_ids,
        "source_learning_hashes": library.source_learning_hashes,
        "manual_status": "accepted",
        "manual_decision": "manual_skill_activation_accepted",
        "manual_allowed": True,
        "activation_apply_allowed": True,
        "next_action": "prepare_skill_activation_apply",
        "blockers": [],
        "manual_hash": "e" * 64,
        "reasons": ["manual_choice_recorded"],
    }
    payload.update(overrides)
    record = CortexManualSkillActivationRecord(**payload)
    CortexManualSkillActivationJsonlStore(profile / CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME).save([record])
    return record


def test_skill_activation_apply_marks_effective_active_from_manual_choice(tmp_path) -> None:
    profile = tmp_path / "profile"
    library = _library(profile)
    manual = _manual(profile, library)

    payload = build_cortex_skill_activation_apply(profile)
    record = payload["apply_records"][0]

    assert record["apply_allowed"] is True
    assert record["apply_status"] == "applied"
    assert record["apply_decision"] == "skill_activation_applied"
    assert record["effective_active"] is True
    assert record["activation_source"] == "manual_operator_choice"
    assert record["next_action"] == "skill_available_for_controlled_use"
    assert record["source_manual_id"] == manual.manual_id
    assert record["source_library_hash"] == library.library_hash
    assert len(record["apply_hash"]) == 64


def test_skill_activation_apply_blocks_hold_choice(tmp_path) -> None:
    profile = tmp_path / "profile"
    library = _library(profile)
    _manual(
        profile,
        library,
        operator_choice="hold",
        manual_decision="manual_skill_activation_held",
        activation_apply_allowed=False,
        next_action="await_manual_skill_activation",
    )

    record = build_cortex_skill_activation_apply(profile)["apply_records"][0]

    assert record["apply_allowed"] is False
    assert record["effective_active"] is False
    assert "manual_choice_not_activate" in record["blockers"]


def test_skill_activation_apply_is_idempotent_by_manual_hash(tmp_path) -> None:
    profile = tmp_path / "profile"
    library = _library(profile)
    _manual(profile, library)

    first = build_cortex_skill_activation_apply(profile)
    second = build_cortex_skill_activation_apply(profile)

    assert len(first["apply_records"]) == 1
    assert second["apply_records"] == []
    assert second["apply_count"] == 1


def test_skill_activation_apply_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    library = _library(profile)
    _manual(profile, library)
    build_cortex_skill_activation_apply(profile)

    summary = summarize_cortex_skill_activation_applies(
        profile / CORTEX_SKILL_ACTIVATION_APPLY_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_skill_activation_apply"
    assert summary["total_apply_count"] == 1
    assert summary["allowed_apply_count"] == 1
    assert summary["effective_active_count"] == 1
    assert summary["latest_apply_allowed"] is True
    assert summary["latest_effective_active"] is True
