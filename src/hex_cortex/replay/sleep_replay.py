"""Batch replay pass for HEX-CORTEX."""

from __future__ import annotations

from hex_cortex.memory.schemas import MemoryRecord
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import (
    ReplayReport,
    ReplayStatus,
    SleepReplayReport,
    SleepReplayStatus,
)
from hex_cortex.spine.canonical_spine import CanonicalSpine


class SleepReplay:
    """Batch wrapper for replay passes."""

    def __init__(
        self,
        *,
        spine: CanonicalSpine,
        replay_engine: ReplayEngine | None = None,
    ) -> None:
        self.spine = spine
        self.replay_engine = replay_engine or ReplayEngine(spine=spine)

    def run(self, task_ids: list[str] | None = None) -> SleepReplayReport:
        selected_task_ids = self._task_ids(task_ids)
        if not selected_task_ids:
            return SleepReplayReport(
                status=SleepReplayStatus.EMPTY,
                requested_task_count=0,
                consolidated_count=0,
                empty_count=0,
                failed_count=0,
                memory_count=0,
                reason="no_task_ids",
            )

        reports = [self.replay_engine.replay_task(task_id) for task_id in selected_task_ids]
        consolidated = [
            report for report in reports if report.status == ReplayStatus.CONSOLIDATED
        ]
        empty = [report for report in reports if report.status == ReplayStatus.EMPTY]
        failed = [
            report for report in reports if report.status == ReplayStatus.INTEGRITY_FAILED
        ]
        memories = self.memories_from_reports(reports)
        status = self._status(consolidated, empty, failed)

        return SleepReplayReport(
            status=status,
            requested_task_count=len(selected_task_ids),
            consolidated_count=len(consolidated),
            empty_count=len(empty),
            failed_count=len(failed),
            memory_count=len(memories),
            reports=reports,
            reason=self._reason(status),
        )

    @staticmethod
    def memories_from_reports(reports: list[ReplayReport]) -> list[MemoryRecord]:
        return [report.memory for report in reports if report.memory is not None]

    def _task_ids(self, task_ids: list[str] | None) -> list[str]:
        if task_ids is not None:
            return _dedupe([task_id for task_id in task_ids if task_id.strip()])
        return _dedupe([event.task_id for event in self.spine.events])

    @staticmethod
    def _status(
        consolidated: list[ReplayReport],
        empty: list[ReplayReport],
        failed: list[ReplayReport],
    ) -> SleepReplayStatus:
        if failed:
            return SleepReplayStatus.INTEGRITY_FAILED
        if consolidated and empty:
            return SleepReplayStatus.PARTIAL
        if consolidated:
            return SleepReplayStatus.COMPLETED
        return SleepReplayStatus.EMPTY

    @staticmethod
    def _reason(status: SleepReplayStatus) -> str | None:
        if status == SleepReplayStatus.INTEGRITY_FAILED:
            return "one_or_more_replays_failed_integrity"
        if status == SleepReplayStatus.PARTIAL:
            return "some_tasks_had_no_events"
        if status == SleepReplayStatus.EMPTY:
            return "no_tasks_consolidated"
        return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
