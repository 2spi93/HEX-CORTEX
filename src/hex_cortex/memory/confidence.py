"""Explicit memory confidence confirmation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.schemas import MemoryRecord


class MemoryConfidenceAuditRecord(BaseModel):
    """One audit entry for a memory confidence update."""

    audit_id: str = Field(default_factory=lambda: f"memconf_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    memory_id: str
    reason: str
    before_confidence: float = Field(ge=0.0, le=1.0)
    after_confidence: float = Field(ge=0.0, le=1.0)
    delta: float
    changed: bool
    before_access_count: int = Field(ge=0)
    after_access_count: int = Field(ge=0)


class MemoryConfidenceReport(BaseModel):
    """Result of confirming one memory."""

    memory_id: str
    reason: str
    found: bool
    changed: bool
    before_confidence: float | None = None
    after_confidence: float | None = None
    delta: float = 0.0
    before_access_count: int | None = None
    after_access_count: int | None = None


class MemoryConfidencePlanCandidate(BaseModel):
    """One memory candidate recommended for confidence confirmation."""

    memory_id: str
    title: str
    memory_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    access_count: int = Field(ge=0)
    visible: bool
    priority_score: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


class MemoryConfidencePlan(BaseModel):
    """Non-mutating plan for memory confidence confirmations."""

    total_memory_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    candidates: list[MemoryConfidencePlanCandidate]


class MemoryConfidencePlanner:
    """Rank memories that should be confirmed next."""

    def __init__(self, confidence_floor: float = 0.7) -> None:
        self.confidence_floor = confidence_floor

    def plan(
        self,
        memories: list[MemoryRecord],
        *,
        limit: int = 5,
    ) -> MemoryConfidencePlan:
        """Return a non-mutating confidence confirmation plan."""

        if limit <= 0:
            raise ValueError("memory confidence plan limit must be positive")

        candidates = [
            self._candidate(memory)
            for memory in memories
            if memory.visible and self._needs_confirmation(memory)
        ]
        candidates.sort(
            key=lambda candidate: (
                -candidate.priority_score,
                candidate.confidence,
                candidate.access_count,
                candidate.memory_id,
            )
        )
        selected = candidates[:limit]
        return MemoryConfidencePlan(
            total_memory_count=len(memories),
            candidate_count=len(selected),
            candidates=selected,
        )

    def _needs_confirmation(self, memory: MemoryRecord) -> bool:
        return memory.confidence < self.confidence_floor or memory.access_count == 0

    def _candidate(self, memory: MemoryRecord) -> MemoryConfidencePlanCandidate:
        reasons = []
        if memory.confidence < self.confidence_floor:
            reasons.append("confidence_below_floor")
        if memory.access_count == 0:
            reasons.append("never_confirmed")
        confidence_gap = max(0.0, self.confidence_floor - memory.confidence)
        access_bonus = 0.2 if memory.access_count == 0 else 0.0
        priority_score = min(1.0, round(confidence_gap + access_bonus, 4))
        return MemoryConfidencePlanCandidate(
            memory_id=memory.memory_id,
            title=memory.title,
            memory_type=memory.memory_type.value,
            confidence=memory.confidence,
            access_count=memory.access_count,
            visible=memory.visible,
            priority_score=priority_score,
            reasons=reasons,
        )


class MemoryConfidenceUpdater:
    """Apply explicit confidence confirmations to memory records."""

    def __init__(self, delta: float = 0.05) -> None:
        if delta <= 0:
            raise ValueError("confidence delta must be positive")
        self.delta = delta

    def confirm(
        self,
        memories: list[MemoryRecord],
        *,
        memory_id: str,
        reason: str,
    ) -> tuple[list[MemoryRecord], MemoryConfidenceReport]:
        """Confirm one memory and return updated copies plus a report."""

        updated: list[MemoryRecord] = []
        found_report: MemoryConfidenceReport | None = None
        now = datetime.now(UTC).isoformat()
        for memory in memories:
            if memory.memory_id != memory_id:
                updated.append(memory.model_copy(deep=True))
                continue

            before_confidence = memory.confidence
            before_access_count = memory.access_count
            after_confidence = min(1.0, round(before_confidence + self.delta, 4))
            after_access_count = before_access_count + 1
            confidence_changed = after_confidence != before_confidence
            access_count_changed = after_access_count != before_access_count
            changed = confidence_changed or access_count_changed
            updated_memory = memory.model_copy(
                update={
                    "confidence": after_confidence,
                    "access_count": after_access_count,
                    "last_accessed_at": now,
                },
                deep=True,
            )
            updated.append(updated_memory)
            found_report = MemoryConfidenceReport(
                memory_id=memory_id,
                reason=reason,
                found=True,
                changed=changed,
                before_confidence=before_confidence,
                after_confidence=after_confidence,
                delta=round(after_confidence - before_confidence, 4),
                before_access_count=before_access_count,
                after_access_count=after_access_count,
            )
        if found_report is not None:
            return updated, found_report
        return updated, MemoryConfidenceReport(
            memory_id=memory_id,
            reason=reason,
            found=False,
            changed=False,
        )


class MemoryConfidenceAuditJsonlStore:
    """Persist memory confidence audit records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[MemoryConfidenceAuditRecord]:
        """Load memory confidence audit records."""

        if not self.path.exists():
            return []

        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    records.append(MemoryConfidenceAuditRecord.model_validate(payload))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid memory confidence record at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[MemoryConfidenceAuditRecord]) -> int:
        """Replace JSONL content with audit records."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: MemoryConfidenceAuditRecord) -> int:
        """Append one audit record and return the new count."""

        records = self.load()
        records.append(record)
        return self.save(records)
