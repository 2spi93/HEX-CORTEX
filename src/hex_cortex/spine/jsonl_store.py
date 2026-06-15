"""JSONL persistence for the HEX-CORTEX canonical spine."""

from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.schemas import CanonicalSpineEvent


class CanonicalSpineJsonlStore:
    """Persist canonical spine events as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, spine: CanonicalSpine) -> int:
        """Write all spine events to JSONL and return the number written."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        events = spine.events
        with self.path.open("w", encoding="utf-8") as handle:
            for event in events:
                line = event.model_dump_json()
                handle.write(f"{line}\n")
        return len(events)

    def append_event(self, event: CanonicalSpineEvent) -> None:
        """Append one already-built canonical event to JSONL."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{event.model_dump_json()}\n")

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
