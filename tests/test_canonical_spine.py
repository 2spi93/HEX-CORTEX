from datetime import UTC, datetime

from hex_cortex.spine.canonical_spine import CanonicalSpine


def test_spine_appends_hash_chained_events() -> None:
    spine = CanonicalSpine()

    first = spine.append(
        event_type="task.received",
        task_id="task_1",
        source="test",
        payload={"goal": "build cortex"},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = spine.append(
        event_type="routing.decision",
        task_id="task_1",
        source="router",
        payload={"mode": "deep"},
        confidence=0.82,
        created_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )

    assert first.sequence_number == 1
    assert first.prev_event_hash is None
    assert second.sequence_number == 2
    assert second.prev_event_hash == first.event_hash
    assert spine.verify_integrity().ok is True


def test_spine_projects_counts_and_latest_hash() -> None:
    spine = CanonicalSpine()
    spine.append(event_type="task.received", task_id="task_1", source="test")
    latest = spine.append(event_type="task.received", task_id="task_2", source="test")
    spine.append(event_type="memory.compressed", task_id="task_1", source="memory")

    projection = spine.project()

    assert projection.total_events == 3
    assert projection.task_count == 2
    assert projection.event_type_counts["task.received"] == 2
    assert projection.latest_sequence_number == 3
    assert projection.latest_event_hash != latest.event_hash


def test_spine_filters_events_for_task_and_latest_by_type() -> None:
    spine = CanonicalSpine()
    spine.append(event_type="task.received", task_id="task_1", source="test")
    spine.append(event_type="task.received", task_id="task_2", source="test")
    latest = spine.append(event_type="memory.compressed", task_id="task_1", source="memory")

    task_events = spine.events_for_task("task_1")
    latest_memory = spine.latest_by_type("memory.compressed")

    assert [event.event_type for event in task_events] == ["task.received", "memory.compressed"]
    assert latest_memory is not None
    assert latest_memory.event_hash == latest.event_hash


def test_spine_detects_internal_tampering() -> None:
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received",
        task_id="task_1",
        source="test",
        payload={"goal": "safe"},
    )
    spine.append(
        event_type="action.decided",
        task_id="task_1",
        source="action",
        payload={"decision": "answer"},
    )

    # Deliberately mutate private state to verify the integrity checker.
    spine._events[0].payload["goal"] = "tampered"  # noqa: SLF001

    report = spine.verify_integrity()

    assert report.ok is False
    assert report.reason == "event_hash_mismatch"
    assert report.first_broken_sequence_number == 1
