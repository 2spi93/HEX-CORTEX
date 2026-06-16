"""Summaries for memory confidence audit records."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore


class MemoryConfidenceAuditSummary(BaseModel):
    """Aggregate view of memory confidence audit activity."""

    inspect_type: str = "memory_confidence_audit_summary"
    path: str
    exists: bool
    total_audit_count: int = Field(ge=0)
    positive_delta_count: int = Field(ge=0)
    negative_delta_count: int = Field(ge=0)
    zero_delta_count: int = Field(ge=0)
    total_positive_delta: float
    total_negative_delta: float
    net_delta: float
    reason_counts: dict[str, int]
    latest_audit_id: str | None
    latest_memory_id: str | None
    latest_reason: str | None
    latest_delta: float | None


def summarize_memory_confidence_audit(path: Path) -> dict[str, object]:
    """Summarize positive, negative, and net memory confidence changes."""

    records = MemoryConfidenceAuditJsonlStore(path).load()
    latest = records[-1] if records else None
    positive_deltas = [record.delta for record in records if record.delta > 0]
    negative_deltas = [record.delta for record in records if record.delta < 0]
    zero_delta_count = sum(1 for record in records if record.delta == 0)
    reason_counts = Counter(record.reason for record in records)
    summary = MemoryConfidenceAuditSummary(
        path=str(path),
        exists=path.exists(),
        total_audit_count=len(records),
        positive_delta_count=len(positive_deltas),
        negative_delta_count=len(negative_deltas),
        zero_delta_count=zero_delta_count,
        total_positive_delta=round(sum(positive_deltas), 4),
        total_negative_delta=round(sum(negative_deltas), 4),
        net_delta=round(sum(record.delta for record in records), 4),
        reason_counts=dict(sorted(reason_counts.items())),
        latest_audit_id=latest.audit_id if latest else None,
        latest_memory_id=latest.memory_id if latest else None,
        latest_reason=latest.reason if latest else None,
        latest_delta=latest.delta if latest else None,
    )
    return summary.model_dump(mode="json")
