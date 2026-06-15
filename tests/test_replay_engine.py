from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import ReplayStatus
from hex_cortex.spine.canonical_spine import CanonicalSpine


def test_replay_engine_returns_empty_report_for_unknown_task() -> None:
    spine = CanonicalSpine()
    engine = ReplayEngine(spine=spine)

    report = engine.replay_task("missing_task")

    assert report.status == ReplayStatus.EMPTY
    assert report.event_count == 0
    assert report.reason == "no_events_for_task"


def test_replay_engine_consolidates_successful_task() -> None:
    spine = CanonicalSpine()
    task_id = "task_1"
    spine.append(
        event_type="task.received",
        task_id=task_id,
        source="test",
        payload={"goal": "build replay memory"},
    )
    spine.append(
        event_type="routing.decision",
        task_id=task_id,
        source="router",
        payload={"selected_cells": ["memory_cell", "critic_cell"]},
        confidence=0.8,
    )
    spine.append(
        event_type="retrieval.packet",
        task_id=task_id,
        source="memory",
        payload={"used_memory_ids": ["mem_1"]},
        confidence=0.7,
    )
    spine.append(
        event_type="clock.completed",
        task_id=task_id,
        source="clock",
        payload={"completed": True},
        confidence=0.9,
    )

    report = ReplayEngine(spine=spine).replay_task(task_id)

    assert report.status == ReplayStatus.CONSOLIDATED
    assert report.event_count == 4
    assert report.episode is not None
    assert report.episode.goal == "build replay memory"
    assert report.episode.active_cells == ["memory_cell", "critic_cell"]
    assert report.episode.used_memory_ids == ["mem_1"]
    assert report.compression is not None
    assert report.compression.extracted_rules
    assert report.memory is not None
    assert "tacit-rule" in report.memory.tags


def test_replay_engine_consolidates_failed_task_with_error_rule() -> None:
    spine = CanonicalSpine()
    task_id = "task_2"
    spine.append(
        event_type="task.received",
        task_id=task_id,
        source="test",
        payload={"goal": "execute risky action"},
    )
    spine.append(
        event_type="tick.completed",
        task_id=task_id,
        source="clock",
        payload={"status": "failed", "error": "critic rejected action"},
        confidence=0.3,
    )
    spine.append(
        event_type="clock.completed",
        task_id=task_id,
        source="clock",
        payload={"completed": False},
        confidence=0.2,
    )

    report = ReplayEngine(spine=spine).replay_task(task_id)

    assert report.status == ReplayStatus.CONSOLIDATED
    assert report.episode is not None
    assert report.episode.errors == ["critic rejected action", "failed event: tick.completed"]
    assert report.compression is not None
    assert "CriticCell" in report.compression.extracted_rules[0].claim


def test_replay_engine_blocks_when_spine_integrity_fails() -> None:
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received",
        task_id="task_3",
        source="test",
        payload={"goal": "tamper test"},
    )
    spine._events[0].payload["goal"] = "tampered"

    report = ReplayEngine(spine=spine).replay_task("task_3")

    assert report.status == ReplayStatus.INTEGRITY_FAILED
    assert report.spine_integrity_ok is False
    assert report.reason == "event_hash_mismatch"
