from hex_cortex.memory.cortex_skill_activation_gate import (
    CORTEX_SKILL_ACTIVATION_GATE_FILENAME,
    build_cortex_skill_activation_gate,
    summarize_cortex_skill_activation_gates,
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


def test_cortex_skill_activation_gate_authorizes_registered_inactive_skill(tmp_path) -> None:
    profile = tmp_path / "profile"
    library = _library(profile)

    payload = build_cortex_skill_activation_gate(profile)
    record = payload["gate_records"][0]

    assert record["gate_allowed"] is True
    assert record["gate_status"] == "ready"
    assert record["gate_decision"] == "skill_activation_gate_ready"
    assert record["activation_authorized"] is True
    assert record["activation_mode"] == "manual_enablement_required"
    assert record["next_action"] == "await_manual_skill_activation"
    assert record["source_library_id"] == library.library_id
    assert record["source_library_hash"] == library.library_hash
    assert len(record["gate_hash"]) == 64


def test_cortex_skill_activation_gate_blocks_active_skill(tmp_path) -> None:
    profile = tmp_path / "profile"
    _library(profile, active=True, activation_status="active")

    record = build_cortex_skill_activation_gate(profile)["gate_records"][0]

    assert record["gate_allowed"] is False
    assert record["activation_authorized"] is False
    assert "skill_already_active" in record["blockers"]


def test_cortex_skill_activation_gate_is_idempotent_by_library_hash(tmp_path) -> None:
    profile = tmp_path / "profile"
    _library(profile)

    first = build_cortex_skill_activation_gate(profile)
    second = build_cortex_skill_activation_gate(profile)

    assert len(first["gate_records"]) == 1
    assert second["gate_records"] == []
    assert second["gate_count"] == 1


def test_cortex_skill_activation_gate_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _library(profile)
    build_cortex_skill_activation_gate(profile)

    summary = summarize_cortex_skill_activation_gates(
        profile / CORTEX_SKILL_ACTIVATION_GATE_FILENAME
    )

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_skill_activation_gate"
    assert summary["total_gate_count"] == 1
    assert summary["allowed_gate_count"] == 1
    assert summary["authorized_activation_count"] == 1
    assert summary["latest_gate_allowed"] is True
    assert summary["latest_activation_authorized"] is True
    assert summary["latest_next_action"] == "await_manual_skill_activation"
