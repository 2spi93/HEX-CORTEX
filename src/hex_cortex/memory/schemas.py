"""Typed contracts for HEX-CORTEX memory and retrieval."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class MemorySensitivity(StrEnum):
    """Sensitivity level for stored memory."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RetrievalMethod(StrEnum):
    """Retrieval method used to build a context packet."""

    EXACT = "exact"
    LEXICAL = "lexical"
    SEMANTIC_FALLBACK = "semantic_fallback"
    EMPTY = "empty"


class MemoryRecord(BaseModel):
    """A compressed memory unit.

    This is not a raw transcript. It is a typed, source-linked memory candidate.
    """

    memory_id: str = Field(default_factory=lambda: f"mem_{uuid4().hex}")
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    sensitivity: MemorySensitivity = MemorySensitivity.LOW
    visible: bool = True
    deletable: bool = True
    reason_for_storage: str | None = None

    @field_validator("title", "body")
    @classmethod
    def text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("memory text fields must not be empty")
        return value


class IndexEntry(BaseModel):
    """Local index entry for a note, chunk, or compressed memory."""

    entry_id: str = Field(default_factory=lambda: f"idx_{uuid4().hex}")
    path: str
    title: str
    text: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("path", "title", "text")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("index entry fields must not be empty")
        return value


class RetrievalQuery(BaseModel):
    """A bounded memory query."""

    query: str
    top_k: int = Field(default=8, ge=1, le=32)
    max_context_chars: int = Field(default=8_000, ge=256, le=64_000)
    semantic_fallback_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    required_tags: list[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("retrieval query must not be empty")
        return value


class RetrievalResult(BaseModel):
    """One retrieved memory/index hit."""

    entry_id: str
    path: str
    title: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)
    method: RetrievalMethod
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextPacket(BaseModel):
    """Small context packet injected into the workspace."""

    packet_id: str = Field(default_factory=lambda: f"ctx_{uuid4().hex}")
    query: str
    method: RetrievalMethod
    results: list[RetrievalResult] = Field(default_factory=list)
    context_text: str = ""
    total_chars: int = Field(default=0, ge=0)
    truncated: bool = False


class CompressionRecord(BaseModel):
    """A record of memory compression from raw material to reusable knowledge."""

    compression_id: str = Field(default_factory=lambda: f"cmp_{uuid4().hex}")
    source_event_ids: list[str]
    summary: str
    extracted_rules: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SurpriseEvent(BaseModel):
    """Difference between expected and observed outcome."""

    surprise_id: str = Field(default_factory=lambda: f"sur_{uuid4().hex}")
    prediction_id: str
    actual_event_id: str
    surprise_score: float = Field(ge=0.0, le=1.0)
    explanation: str
