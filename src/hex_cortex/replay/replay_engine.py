"""Replay engine for HEX-CORTEX."""

from __future__ import annotations

from statistics import fmean
from typing import Any

from hex_cortex.memory.compression import MemoryCompressionSpine
from hex_cortex.memory.schemas import ReplayOutcome
from hex_cortex.replay.schemas import ReplayReport, ReplayStatus
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.schemas import CanonicalSpineEvent


class ReplayEngine:
    """Consolidate canonical spine events into compressed memory."""

    def __init__(
        self,
        *,
        spine: CanonicalSpine,
        compressor: MemoryCompressionSpine | None = None,
    ) -> None:
        self.spine = spine
        self.compressor = compressor or MemoryCompressionSpine()

    def replay_task(self, task_id: str) -> ReplayReport:
        integrity = self.spine.verify_integrity()
        if not integrity.ok:
            return ReplayReport(
                task_id=task_id,
                status=ReplayStatus.INTEGRITY_FAILED,
                event_count=0,
                spine_integrity_ok=False,
                reason=integrity.reason,
            )

        events = self.spine.events_for_task(task_id)
        if not events:
            return ReplayReport(
                task_id=task_id,
                status=ReplayStatus.EMPTY,
                event_count=0,
                spine_integrity_ok=True,
                reason="no_events_for_task",
            )

        source_event_ids = [event.event_id for event in events]
        episode = self.compressor.summarize_episode(
            task_id=task_id,
            goal=self._goal(task_id, events),
            active_cells=self._active_cells(events),
            observations=self._observations(events),
            errors=self._errors(events),
            used_memory_ids=self._memory_ids(events),
            outcome=self._outcome(events),
            confidence=self._confidence(events),
        )
        compression = self.compressor.compress_episode(
            episode,
            source_event_ids=source_event_ids,
        )
        memory = self.compressor.to_memory_record(compression)

        return ReplayReport(
            task_id=task_id,
            status=ReplayStatus.CONSOLIDATED,
            event_count=len(events),
            source_event_ids=source_event_ids,
            spine_integrity_ok=True,
            episode=episode,
            compression=compression,
            memory=memory,
        )

    @staticmethod
    def _goal(task_id: str, events: list[CanonicalSpineEvent]) -> str:
        for event in events:
            for key in ("goal", "content"):
                value = event.payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return f"Replay task {task_id}"

    @staticmethod
    def _active_cells(events: list[CanonicalSpineEvent]) -> list[str]:
        values: list[str] = []
        for event in events:
            values.extend(_string_list(event.payload.get("active_cells")))
            values.extend(_string_list(event.payload.get("selected_cells")))
            cell_id = event.payload.get("cell_id")
            if isinstance(cell_id, str) and cell_id.strip():
                values.append(cell_id)
        return _dedupe(values)

    @staticmethod
    def _memory_ids(events: list[CanonicalSpineEvent]) -> list[str]:
        values: list[str] = []
        for event in events:
            values.extend(_string_list(event.payload.get("used_memory_ids")))
            values.extend(_string_list(event.payload.get("memory_ids")))
        return _dedupe(values)

    @staticmethod
    def _observations(events: list[CanonicalSpineEvent]) -> list[str]:
        values: list[str] = []
        for event in events:
            values.extend(_string_list(event.payload.get("observations")))
            observation = event.payload.get("observation")
            if isinstance(observation, str) and observation.strip():
                values.append(observation)
            if event.event_type in {"routing.decision", "memory.compressed"}:
                values.append(f"{event.event_type} from {event.source}")
        return _dedupe(values)

    @staticmethod
    def _errors(events: list[CanonicalSpineEvent]) -> list[str]:
        values: list[str] = []
        for event in events:
            values.extend(_string_list(event.payload.get("errors")))
            error = event.payload.get("error")
            if isinstance(error, str) and error.strip():
                values.append(error)
            if event.payload.get("status") == "failed":
                values.append(f"failed event: {event.event_type}")
        return _dedupe(values)

    @staticmethod
    def _outcome(events: list[CanonicalSpineEvent]) -> ReplayOutcome:
        for event in reversed(events):
            if event.event_type == "clock.completed":
                completed = event.payload.get("completed")
                if completed is True:
                    return ReplayOutcome.SUCCESS
                if completed is False:
                    return ReplayOutcome.FAILURE
        if ReplayEngine._errors(events):
            return ReplayOutcome.FAILURE
        return ReplayOutcome.UNKNOWN

    @staticmethod
    def _confidence(events: list[CanonicalSpineEvent]) -> float:
        values = [event.confidence for event in events if event.confidence is not None]
        if not values:
            return 0.5
        return round(fmean(values), 10)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
