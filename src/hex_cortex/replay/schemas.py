"""Replay schemas for HEX-CORTEX."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from hex_cortex.memory.schemas import CompressionRecord, EpisodeSummary, MemoryRecord


class ReplayStatus(StrEnum):
    """Replay consolidation status."""

    EMPTY = "empty"
    CONSOLIDATED = "consolidated"
    INTEGRITY_FAILED = "integrity_failed"


class ReplayReport(BaseModel):
    """Result of replaying one task from canonical events."""

    task_id: str
    status: ReplayStatus
    event_count: int = Field(ge=0)
    source_event_ids: list[str] = Field(default_factory=list)
    spine_integrity_ok: bool
    episode: EpisodeSummary | None = None
    compression: CompressionRecord | None = None
    memory: MemoryRecord | None = None
    reason: str | None = None
