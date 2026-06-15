"""Append-only canonical spine for HEX-CORTEX.

The spine records cognitive events with hash chaining so they can be replayed and verified.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from hex_cortex.spine.schemas import CanonicalSpineEvent, SpineIntegrityReport, SpineProjection


class CanonicalSpine:
    """Append-only event spine with hash-chain verification."""

    def __init__(self) -> None:
        self._events: list[CanonicalSpineEvent] = []

    @property
    def events(self) -> list[CanonicalSpineEvent]:
        return [event.model_copy(deep=True) for event in self._events]

    def append(
        self,
        *,
        event_type: str,
        task_id: str,
        source: str,
        payload: dict[str, Any] | None = None,
        confidence: float | None = None,
        correlation_keys: dict[str, str] | None = None,
        created_at: datetime | None = None,
    ) -> CanonicalSpineEvent:
        sequence_number = len(self._events) + 1
        prev_hash = self._events[-1].event_hash if self._events else None
        timestamp = created_at or datetime.now(UTC)
        safe_payload = payload or {}
        safe_correlation_keys = correlation_keys or {}

        event_hash = self.compute_hash(
            sequence_number=sequence_number,
            event_type=event_type,
            task_id=task_id,
            source=source,
            payload=safe_payload,
            confidence=confidence,
            correlation_keys=safe_correlation_keys,
            created_at=timestamp,
            prev_event_hash=prev_hash,
        )

        event = CanonicalSpineEvent(
            sequence_number=sequence_number,
            event_type=event_type,
            task_id=task_id,
            source=source,
            payload=safe_payload,
            confidence=confidence,
            correlation_keys=safe_correlation_keys,
            created_at=timestamp,
            prev_event_hash=prev_hash,
            event_hash=event_hash,
        )
        self._events.append(event)
        return event.model_copy(deep=True)

    def replace_events(self, events: list[CanonicalSpineEvent]) -> None:
        """Replace the in-memory event list with a verified event sequence."""

        previous_events = self._events
        self._events = [event.model_copy(deep=True) for event in events]
        integrity = self.verify_integrity()
        if integrity.ok:
            return
        self._events = previous_events
        reason = integrity.reason or "unknown_integrity_error"
        raise ValueError(f"invalid canonical spine events: {reason}")

    def events_for_task(self, task_id: str) -> list[CanonicalSpineEvent]:
        return [event.model_copy(deep=True) for event in self._events if event.task_id == task_id]

    def latest_by_type(self, event_type: str) -> CanonicalSpineEvent | None:
        for event in reversed(self._events):
            if event.event_type == event_type:
                return event.model_copy(deep=True)
        return None

    def project(self) -> SpineProjection:
        event_type_counts = Counter(event.event_type for event in self._events)
        task_ids = {event.task_id for event in self._events}
        latest = self._events[-1] if self._events else None
        return SpineProjection(
            total_events=len(self._events),
            task_count=len(task_ids),
            event_type_counts=dict(event_type_counts),
            latest_sequence_number=latest.sequence_number if latest else None,
            latest_event_hash=latest.event_hash if latest else None,
        )

    def verify_integrity(self) -> SpineIntegrityReport:
        previous_hash: str | None = None

        for expected_sequence, event in enumerate(self._events, start=1):
            if event.sequence_number != expected_sequence:
                return SpineIntegrityReport(
                    ok=False,
                    checked_events=expected_sequence - 1,
                    first_broken_sequence_number=event.sequence_number,
                    reason="sequence_number_gap_or_reorder",
                )

            if event.prev_event_hash != previous_hash:
                return SpineIntegrityReport(
                    ok=False,
                    checked_events=expected_sequence - 1,
                    first_broken_sequence_number=event.sequence_number,
                    reason="previous_hash_mismatch",
                )

            expected_hash = self.compute_hash(
                sequence_number=event.sequence_number,
                event_type=event.event_type,
                task_id=event.task_id,
                source=event.source,
                payload=event.payload,
                confidence=event.confidence,
                correlation_keys=event.correlation_keys,
                created_at=event.created_at,
                prev_event_hash=event.prev_event_hash,
            )
            if event.event_hash != expected_hash:
                return SpineIntegrityReport(
                    ok=False,
                    checked_events=expected_sequence - 1,
                    first_broken_sequence_number=event.sequence_number,
                    reason="event_hash_mismatch",
                )

            previous_hash = event.event_hash

        return SpineIntegrityReport(ok=True, checked_events=len(self._events))

    @staticmethod
    def compute_hash(
        *,
        sequence_number: int,
        event_type: str,
        task_id: str,
        source: str,
        payload: dict[str, Any],
        confidence: float | None,
        correlation_keys: dict[str, str],
        created_at: datetime,
        prev_event_hash: str | None,
    ) -> str:
        canonical_payload = {
            "sequence_number": sequence_number,
            "event_type": event_type,
            "task_id": task_id,
            "source": source,
            "payload": payload,
            "confidence": confidence,
            "correlation_keys": correlation_keys,
            "created_at": created_at.isoformat(),
            "prev_event_hash": prev_event_hash,
        }
        encoded = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
