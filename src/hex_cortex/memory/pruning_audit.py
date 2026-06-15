"""Local JSONL audit records for memory pruning operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field


class PruningAuditRecord(BaseModel):
    """One local operator audit entry for a pruning command."""

    audit_id: str = Field(default_factory=lambda: f"audit_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    operation: str
    profile_path: str
    memory_path: str
    backup_path: str | None = None
    dry_run: bool
    applied: bool
    total_memory_count: int = Field(ge=0)
    changed_count: int = Field(ge=0)
    visible_before: int = Field(ge=0)
    visible_after: int = Field(ge=0)
    keep_count: int = Field(ge=0)
    degrade_count: int = Field(ge=0)
    archive_count: int = Field(ge=0)


class PruningAuditJsonlStore:
    """Persist pruning audit records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[PruningAuditRecord]:
        """Load audit records from JSONL."""

        if not self.path.exists():
            return []

        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    records.append(PruningAuditRecord.model_validate(payload))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid pruning audit record at line {line_number}") from exc
        return records

    def save(self, records: list[PruningAuditRecord]) -> int:
        """Replace JSONL content with audit records."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: PruningAuditRecord) -> int:
        """Append one audit record and return the new count."""

        records = self.load()
        records.append(record)
        return self.save(records)
