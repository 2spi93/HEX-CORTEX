from hex_cortex.memory.cortex_skill_candidate import (
    CORTEX_SKILL_CANDIDATE_FILENAME,
    CortexSkillCandidateJsonlStore,
    CortexSkillCandidateRecord,
)
from hex_cortex.memory.cortex_skill_library import (
    CORTEX_SKILL_LIBRARY_FILENAME,
    build_cortex_skill_library,
    summarize_cortex_skill_library,
)


def _candidate(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "skill_key": "architecture:e192e479ed25",
        "domain": "architecture",
        "source_learning_ids": ["learning_1"],
        "source_learning_hashes": ["a" * 64],
        "reusable_rule": "Before adding routers or executors, check whether better learning memory is needed.",
        "evidence_count": 1,
        "average_confidence": 0.95,
        "candidate_status": "ready",
        "candidate_decision": "skill_candidate_ready",
        "candidate_allowed": True,
        "promote_to_library": True,
        "blockers": [],
        "next_action": "prepare_skill_library_promotion",
        "candidate_hash": "b" * 64,
        "reasons": ["learning_events_promoted"],
    }
    payload.update(overrides)
    record = CortexSkillCandidateRecord(**payload)
    CortexSkillCandidateJsonlStore(profile / CORTEX_SKILL_CANDIDATE_FILENAME).append_many([record])
    return record


def test_cortex_skill_library_registers_promotable_candidate_inactive(tmp_path) -> None:
    profile = tmp_path / "profile"
    candidate = _candidate(profile)

    payload = build_cortex_skill_library(profile)
    record = payload["library_records"][0]

    assert record["library_allowed"] is True
    assert record["library_status"] == "registered"
    assert record["library_decision"] == "skill_library_registered"
    assert record["active"] is False
    assert record["activation_status"] == "inactive_pending_gate"
    assert record["next_action"] == "await_skill_activation_gate"
    assert record["source_candidate_id"] == candidate.candidate_id
    assert record["source_candidate_hash"] == candidate.candidate_hash
    assert len(record["library_hash"]) == 64


def test_cortex_skill_library_ignores_non_promotable_candidate(tmp_path) -> None:
    profile = tmp_path / "profile"
    _candidate(profile, promote_to_library=False, average_confidence=0.4)

    payload = build_cortex_skill_library(profile)

    assert payload["library_records"] == []


def test_cortex_skill_library_is_idempotent_by_candidate_hash(tmp_path) -> None:
    profile = tmp_path / "profile"
    _candidate(profile)

    first = build_cortex_skill_library(profile)
    second = build_cortex_skill_library(profile)

    assert len(first["library_records"]) == 1
    assert second["library_records"] == []
    assert second["library_count"] == 1


def test_cortex_skill_library_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _candidate(profile)
    build_cortex_skill_library(profile)

    summary = summarize_cortex_skill_library(profile / CORTEX_SKILL_LIBRARY_FILENAME)

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_skill_library"
    assert summary["total_skill_count"] == 1
    assert summary["registered_skill_count"] == 1
    assert summary["active_skill_count"] == 0
    assert summary["latest_library_allowed"] is True
    assert summary["latest_active"] is False
    assert summary["latest_next_action"] == "await_skill_activation_gate"
