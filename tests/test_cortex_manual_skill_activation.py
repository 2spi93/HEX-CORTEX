from hex_cortex.memory.cortex_manual_skill_activation import (
    CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME,
    record_cortex_manual_skill_activation,
    summarize_cortex_manual_skill_activations,
)
from hex_cortex.memory.cortex_skill_activation_gate import (
    CORTEX_SKILL_ACTIVATION_GATE_FILENAME,
    CortexSkillActivationGateJsonlStore,
    CortexSkillActivationGateRecord,
)


def _gate(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "skill_key": "architecture:e192e479ed25",
        "domain": "architecture",
        "source_library_id": "library_1",
        "source_library_hash": "a" * 64,
        "source_candidate_hash": "b" * 64,
        "source_learning_ids": ["learning_1"],
        "source_learning_hashes": ["c" * 64],
        "evidence_count": 1,
        "average_confidence": 0.95,
        "gate_status": "ready",
        "gate_decision": "skill_activation_gate_ready",
        "gate_allowed": True,
        "activation_authorized": True,
        "activation_mode": "manual_enablement_required",
        "next_action": "await_manual_skill_activation",
        "blockers": [],
        "gate_hash": "d" * 64,
        "reasons": ["library_registered"],
    }
    payload.update(overrides)
    record = CortexSkillActivationGateRecord(**payload)
    CortexSkillActivationGateJsonlStore(profile / CORTEX_SKILL_ACTIVATION_GATE_FILENAME).save([record])
    return record


def test_manual_skill_activation_accepts_activate_choice(tmp_path) -> None:
    profile = tmp_path / "profile"
    gate = _gate(profile)

    record = record_cortex_manual_skill_activation(
        profile,
        choice="activate",
        note="operator explicitly approved this skill for the next apply stage",
    )["manual_record"]

    assert record["manual_allowed"] is True
    assert record["manual_decision"] == "manual_skill_activation_accepted"
    assert record["activation_apply_allowed"] is True
    assert record["next_action"] == "prepare_skill_activation_apply"
    assert record["source_gate_id"] == gate.gate_id
    assert len(record["manual_hash"]) == 64


def test_manual_skill_activation_records_hold_without_apply(tmp_path) -> None:
    profile = tmp_path / "profile"
    _gate(profile)

    record = record_cortex_manual_skill_activation(
        profile,
        choice="hold",
        note="operator wants to keep the skill pending for more review",
    )["manual_record"]

    assert record["manual_allowed"] is True
    assert record["manual_decision"] == "manual_skill_activation_held"
    assert record["activation_apply_allowed"] is False
    assert record["next_action"] == "await_manual_skill_activation"


def test_manual_skill_activation_blocks_invalid_choice(tmp_path) -> None:
    profile = tmp_path / "profile"
    _gate(profile)

    record = record_cortex_manual_skill_activation(
        profile,
        choice="maybe",
        note="operator supplied an invalid choice that must be rejected",
    )["manual_record"]

    assert record["manual_allowed"] is False
    assert "invalid_operator_choice" in record["blockers"]


def test_manual_skill_activation_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _gate(profile)
    record_cortex_manual_skill_activation(
        profile,
        choice="activate",
        note="operator explicitly approved this skill for the next apply stage",
    )

    summary = summarize_cortex_manual_skill_activations(
        profile / CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_manual_skill_activation"
    assert summary["total_manual_count"] == 1
    assert summary["allowed_manual_count"] == 1
    assert summary["apply_ready_count"] == 1
    assert summary["latest_operator_choice"] == "activate"
    assert summary["latest_activation_apply_allowed"] is True
