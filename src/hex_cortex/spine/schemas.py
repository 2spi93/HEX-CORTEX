"""Schemas for the HEX-CORTEX canonical spine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class CanonicalSpineEvent(BaseModel):
    """One append-only event in the canonical cognitive spine."""

    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    sequence_number: int = Field(ge=1)
    event_type: str
    task_id: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    correlation_keys: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    prev_event_hash: str | None = None
    event_hash: str

    @field_validator("event_type", "task_id", "source", "event_hash")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("canonical event text fields must not be empty")
        return value


class SpineIntegrityReport(BaseModel):
    """Integrity verification result for a canonical spine."""

    ok: bool
    checked_events: int = Field(ge=0)
    first_broken_sequence_number: int | None = None
    reason: str | None = None


class SpineProjection(BaseModel):
    """Compact projection of spine state."""

    total_events: int = Field(ge=0)
    task_count: int = Field(ge=0)
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    latest_sequence_number: int | None = None
    latest_event_hash: str | None = None
