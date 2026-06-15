"""JSONL persistence for HEX-CORTEX memory records."""

from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.schemas import MemoryRecord


class LocalMemoryJsonlStore:
    """Persist compressed memory records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[MemoryRecord]:
        """Load memory records from JSONL."""

        if not self.path.exists():
            return []

        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    records.append(MemoryRecord.model_validate(payload))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid JSONL memory record at line {line_number}") from exc
        return records

    def save(self, records: list[MemoryRecord]) -> int:
        """Replace JSONL content with memory records."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: MemoryRecord) -> int:
        """Append one memory record and return the new visible count."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{record.model_dump_json()}\n")
        return len(self.load())

    def visible(self) -> list[MemoryRecord]:
        """Return records still visible to retrieval/indexing layers."""

        return [record for record in self.load() if record.visible]
