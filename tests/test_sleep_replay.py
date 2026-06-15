from hex_cortex.replay.schemas import SleepReplayStatus
from hex_cortex.replay.sleep_replay import SleepReplay
from hex_cortex.spine.canonical_spine import CanonicalSpine


def append_successful_task(spine: CanonicalSpine, task_id: str) -> None:
    spine.append(
        event_type="task.received",
        task_id=task_id,
        source="test",
        payload={"goal": f"consolidate {task_id}"},
    )
    spine.append(
        event_type="routing.decision",
        task_id=task_id,
        source="router",
        payload={"selected_cells": ["memory_cell"]},
        confidence=0.8,
    )
    spine.append(
        event_type="clock.completed",
        task_id=task_id,
        source="clock",
        payload={"completed": True},
        confidence=0.9,
    )


def test_sleep_replay_returns_empty_without_tasks() -> None:
    report = SleepReplay(spine=CanonicalSpine()).run()

    assert report.status == SleepReplayStatus.EMPTY
    assert report.requested_task_count == 0
    assert report.memory_count == 0
    assert report.reason == "no_task_ids"


def test_sleep_replay_discovers_task_ids_from_spine() -> None:
    spine = CanonicalSpine()
    append_successful_task(spine, "task_1")
    append_successful_task(spine, "task_2")

    report = SleepReplay(spine=spine).run()
    memories = SleepReplay.memories_from_reports(report.reports)

    assert report.status == SleepReplayStatus.COMPLETED
    assert report.requested_task_count == 2
    assert report.consolidated_count == 2
    assert report.memory_count == 2
    assert len(memories) == 2


def test_sleep_replay_reports_partial_batch_when_some_tasks_are_empty() -> None:
    spine = CanonicalSpine()
    append_successful_task(spine, "task_1")

    report = SleepReplay(spine=spine).run(["task_1", "missing_task"])

    assert report.status == SleepReplayStatus.PARTIAL
    assert report.consolidated_count == 1
    assert report.empty_count == 1
    assert report.reason == "some_tasks_had_no_events"


def test_sleep_replay_blocks_batch_when_integrity_fails() -> None:
    spine = CanonicalSpine()
    append_successful_task(spine, "task_1")
    spine._events[0].payload["goal"] = "tampered"

    report = SleepReplay(spine=spine).run(["task_1"])

    assert report.status == SleepReplayStatus.INTEGRITY_FAILED
    assert report.failed_count == 1
    assert report.reason == "one_or_more_replays_failed_integrity"
