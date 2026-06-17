from hex_cortex.memory.cortex_learning_event import (
    CORTEX_LEARNING_EVENT_FILENAME,
    CortexLearningEventJsonlStore,
    CortexLearningEventRecord,
)
from hex_cortex.memory.cortex_skill_candidate import (
    CORTEX_SKILL_CANDIDATE_FILENAME,
    build_cortex_skill_candidates,
    summarize_cortex_skill_candidates,
)


def _learning(profile, **overrides):
    payload = {
        "profile_path": str(profile),
        "outcome": "correction",
        "domain": "architecture",
        "scope": "self",
        "source_ref": "test",
        "problem": "The system needed mission alignment before adding more routes.",
        "action_taken": "The next step was changed toward reusable learning and skills.",
        "result": "The learning event became a promoted skill candidate source.",
        "lesson": "Mission corrections must be preserved as architectural memory.",
        "reusable_rule": "Before adding routers or executors, check whether better learning memory is needed.",
        "confidence": 0.95,
        "promote_to_skill": True,
        "event_status": "accepted",
        "event_decision": "learning_event_accepted",
        "event_allowed": True,
        "blockers": [],
        "learning_hash": "a" * 64,
        "reasons": ["learning_event_validated"],
    }
    payload.update(overrides)
    record = CortexLearningEventRecord(**payload)
    CortexLearningEventJsonlStore(profile / CORTEX_LEARNING_EVENT_FILENAME).append(record)
    return record


def test_cortex_skill_candidate_builds_from_promoted_learning_event(tmp_path) -> None:
    profile = tmp_path / "profile"
    learning = _learning(profile)

    payload = build_cortex_skill_candidates(profile)
    record = payload["candidate_records"][0]

    assert record["candidate_allowed"] is True
    assert record["candidate_decision"] == "skill_candidate_ready"
    assert record["promote_to_library"] is True
    assert record["domain"] == "architecture"
    assert record["source_learning_ids"] == [learning.learning_id]
    assert record["evidence_count"] == 1
    assert record["average_confidence"] == 0.95
    assert record["next_action"] == "prepare_skill_library_promotion"
    assert len(record["candidate_hash"]) == 64


def test_cortex_skill_candidate_ignores_non_promoted_learning_event(tmp_path) -> None:
    profile = tmp_path / "profile"
    _learning(profile, promote_to_skill=False, confidence=0.4)

    payload = build_cortex_skill_candidates(profile)

    assert payload["candidate_records"] == []


def test_cortex_skill_candidate_groups_same_rule(tmp_path) -> None:
    profile = tmp_path / "profile"
    _learning(profile, learning_hash="b" * 64, confidence=0.8)
    _learning(profile, learning_hash="c" * 64, confidence=1.0)

    record = build_cortex_skill_candidates(profile)["candidate_records"][0]

    assert record["evidence_count"] == 2
    assert record["average_confidence"] == 0.9
    assert len(record["source_learning_hashes"]) == 2


def test_cortex_skill_candidate_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    _learning(profile)
    build_cortex_skill_candidates(profile)

    summary = summarize_cortex_skill_candidates(profile / CORTEX_SKILL_CANDIDATE_FILENAME)

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_skill_candidate"
    assert summary["total_candidate_count"] == 1
    assert summary["allowed_candidate_count"] == 1
    assert summary["promotable_candidate_count"] == 1
    assert summary["latest_domain"] == "architecture"
    assert summary["latest_candidate_allowed"] is True
    assert summary["latest_promote_to_library"] is True
