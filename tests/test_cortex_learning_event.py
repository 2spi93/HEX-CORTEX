from hex_cortex.memory.cortex_learning_event import (
    CORTEX_LEARNING_EVENT_FILENAME,
    record_cortex_learning_event,
    summarize_cortex_learning_events,
)


def _valid_payload(**overrides):
    payload = {
        "outcome": "success",
        "domain": "coding",
        "scope": "self",
        "source_ref": "pytest:unit",
        "problem": "A command intake needed safe classification before routing.",
        "action_taken": "Added allowlisted command classification and blocked execute intents.",
        "result": "Inspect and simulate commands are accepted while execute is blocked.",
        "lesson": "Operator commands must pass through a non executing intake first.",
        "reusable_rule": "Never route destructive commands without a dedicated authorization gate.",
        "confidence": 0.91,
    }
    payload.update(overrides)
    return payload


def test_cortex_learning_event_accepts_valid_coding_success(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = record_cortex_learning_event(profile, **_valid_payload())["learning_record"]

    assert record["event_allowed"] is True
    assert record["event_status"] == "accepted"
    assert record["event_decision"] == "learning_event_accepted"
    assert record["promote_to_skill"] is True
    assert record["domain"] == "coding"
    assert len(record["learning_hash"]) == 64


def test_cortex_learning_event_blocks_invalid_or_poor_lesson(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = record_cortex_learning_event(
        profile,
        **_valid_payload(outcome="magic", lesson="bad", reusable_rule="tiny"),
    )["learning_record"]

    assert record["event_allowed"] is False
    assert "invalid_outcome" in record["blockers"]
    assert "lesson_too_short" in record["blockers"]
    assert "reusable_rule_too_short" in record["blockers"]


def test_cortex_learning_event_does_not_promote_low_confidence(tmp_path) -> None:
    profile = tmp_path / "profile"

    record = record_cortex_learning_event(
        profile,
        **_valid_payload(confidence=0.5),
    )["learning_record"]

    assert record["event_allowed"] is True
    assert record["promote_to_skill"] is False


def test_cortex_learning_event_summary_reads_latest(tmp_path) -> None:
    profile = tmp_path / "profile"
    record_cortex_learning_event(profile, **_valid_payload(confidence=0.8))

    summary = summarize_cortex_learning_events(profile / CORTEX_LEARNING_EVENT_FILENAME)

    assert summary["exists"] is True
    assert summary["inspect_type"] == "cortex_learning_event"
    assert summary["total_learning_count"] == 1
    assert summary["accepted_learning_count"] == 1
    assert summary["promoted_skill_candidate_count"] == 1
    assert summary["latest_event_allowed"] is True
    assert summary["latest_domain"] == "coding"
