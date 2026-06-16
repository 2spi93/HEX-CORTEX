import pytest

from hex_cortex.memory.profile_health_history import (
    ProfileHealthHistoryJsonlStore,
    ProfileHealthHistoryRecord,
    summarize_profile_health_history,
)


def make_record(score: float, status: str = "healthy") -> ProfileHealthHistoryRecord:
    return ProfileHealthHistoryRecord(
        profile_path=".hex-cortex",
        overall_score=score,
        status=status,
        spine_integrity_ok=True,
        total_events=80,
        total_memory_count=6,
        visible_memory_count=6,
        hidden_memory_count=0,
        average_memory_confidence=0.5,
        active_skill_count=1,
        pruning_audit_count=2,
        latest_pruning_operation="apply",
    )


def test_profile_health_history_store_appends_and_loads_records(tmp_path) -> None:
    store = ProfileHealthHistoryJsonlStore(tmp_path / "profile-health.jsonl")
    first = make_record(0.9)
    second = make_record(0.95)

    first_count = store.append(first)
    second_count = store.append(second)
    records = store.load()

    assert first_count == 1
    assert second_count == 2
    assert [record.history_id for record in records] == [first.history_id, second.history_id]


def test_profile_health_history_summary_tracks_up_down_flat_and_empty() -> None:
    empty_summary = summarize_profile_health_history([])
    flat_summary = summarize_profile_health_history([make_record(0.9), make_record(0.9)])
    up_summary = summarize_profile_health_history([make_record(0.9), make_record(0.95)])
    down_summary = summarize_profile_health_history([make_record(0.95), make_record(0.9)])

    assert empty_summary.trend == "none"
    assert flat_summary.trend == "flat"
    assert up_summary.trend == "up"
    assert up_summary.score_delta == 0.05
    assert down_summary.trend == "down"
    assert down_summary.score_delta == -0.05


def test_profile_health_history_store_rejects_invalid_json_line(tmp_path) -> None:
    path = tmp_path / "profile-health.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    store = ProfileHealthHistoryJsonlStore(path)

    with pytest.raises(ValueError, match="invalid profile health record"):
        store.load()
