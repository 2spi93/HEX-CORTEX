"""JSONL persistence for HEX-CORTEX skill records."""

from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.evolver.schemas import SkillRecord, SkillStatus


class SkillJsonlStore:
    """Persist skill records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[SkillRecord]:
        """Load skill records from JSONL."""

        if not self.path.exists():
            return []

        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    records.append(SkillRecord.model_validate(payload))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid JSONL skill record at line {line_number}") from exc
        return records

    def save(self, records: list[SkillRecord]) -> int:
        """Replace JSONL content with skill records."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def active(self) -> list[SkillRecord]:
        """Return active skills that can be hydrated into the skill library."""

        return [skill for skill in self.load() if skill.status == SkillStatus.ACTIVE]
