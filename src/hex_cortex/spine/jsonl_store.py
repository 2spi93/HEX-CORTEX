"""JSONL persistence for the HEX-CORTEX canonical spine."""

from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.cortex_durable_jsonl_v7 import (
    atomic_jsonl_snapshot,
    exclusive_jsonl_writer,
)
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.schemas import CanonicalSpineEvent


class CanonicalSpineJsonlStore:
    """Persist canonical spine events as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, spine: CanonicalSpine) -> int:
        """Write all spine events to JSONL and return the number written."""

        if not spine.verify_integrity().ok:
            raise ValueError("invalid_spine_cannot_save")
        events = spine.events
        with exclusive_jsonl_writer(self.path):
            # A snapshot write is explicit; never silently overwrite a newer
            # chain with a stale in-memory instance.
            current = self.load()
            current_events = current.events
            if current_events and events[:len(current_events)] != current_events:
                raise ValueError("spine_snapshot_would_rewrite_history")
            atomic_jsonl_snapshot(self.path, (row.model_dump_json() for row in events))
        return len(events)

    def append_event(self, event: CanonicalSpineEvent) -> None:
        """Append one already-built canonical event to JSONL."""

        with exclusive_jsonl_writer(self.path):
            current = self.load()
            existing = current.events
            # Crash-safe idempotent retry is allowed only for the same event
            # identity and exact hash-chain payload.
            prior = next((row for row in existing if row.event_id == event.event_id), None)
            if prior is not None:
                if prior != event:
                    raise ValueError("spine_event_id_collision")
                return
            candidate = CanonicalSpine()
            candidate.replace_events([*existing, event])
            atomic_jsonl_snapshot(
                self.path, (row.model_dump_json() for row in candidate.events)
            )

    def load(self) -> CanonicalSpine:
        """Load a spine from JSONL and verify hash-chain integrity."""

        spine = CanonicalSpine()
        if not self.path.exists():
            return spine

        events = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    events.append(CanonicalSpineEvent.model_validate(payload))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid JSONL spine event at line {line_number}") from exc

        spine.replace_events(events)
        integrity = spine.verify_integrity()
        if not integrity.ok:
            reason = integrity.reason or "unknown_integrity_error"
            raise ValueError(f"invalid JSONL spine integrity: {reason}")
        return spine
