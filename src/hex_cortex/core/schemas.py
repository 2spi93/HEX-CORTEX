"""Core contracts for HEX-CORTEX.

The first project rule is simple: cells do not exchange vague prose internally.
They exchange typed, replayable state.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class CognitiveMode(StrEnum):
    """Thinking depth selected by the thalamic router."""

    REFLEX = "reflex"
    WORKING = "working"
    DEEP = "deep"


class CellRole(StrEnum):
    """High-level role of a cognitive cell."""

    INTENT = "intent"
    LOGIC = "logic"
    MEMORY = "memory"
    CRITIC = "critic"
    WORLD_MODEL = "world_model"
    ACTION = "action"
    EVIDENCE = "evidence"
    PLANNER = "planner"
    SAFETY = "safety"


class Task(BaseModel):
    """A user/system task entering the cortex."""

    task_id: str = Field(default_factory=lambda: f"task_{uuid4().hex}")
    content: str
    domain_hints: list[str] = Field(default_factory=list)
    novelty: float = Field(default=0.5, ge=0.0, le=1.0)
    risk: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    latency_budget_ms: int = Field(default=2_000, ge=1)

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task content must not be empty")
        return value


class CognitiveBudget(BaseModel):
    """Bounded reasoning budget for one task."""

    mode: CognitiveMode
    max_ticks: int = Field(ge=1, le=16)
    max_cells: int = Field(ge=1, le=32)
    latency_budget_ms: int = Field(ge=1)
    confidence_threshold: float = Field(ge=0.0, le=1.0)


class CellSpec(BaseModel):
    """A registered cell available to the router."""

    cell_id: str
    role: CellRole
    domains: list[str] = Field(default_factory=list)
    trust_score: float = Field(default=0.75, ge=0.0, le=1.0)
    latency_cost: float = Field(default=0.2, ge=0.0, le=1.0)
    recent_error_penalty: float = Field(default=0.0, ge=0.0, le=1.0)


class RoutingDecision(BaseModel):
    """Router output for a task."""

    task_id: str
    mode: CognitiveMode
    selected_cells: list[str]
    budget: CognitiveBudget
    rationale: str


class Hypothesis(BaseModel):
    """A compact claim proposed by a cell."""

    hypothesis_id: str = Field(default_factory=lambda: f"hyp_{uuid4().hex}")
    claim: str
    source_cell_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)


class WorkspaceState(BaseModel):
    """Compact global cognitive workspace.

    This should stay small enough to inspect, serialize, and replay.
    """

    workspace_id: str = Field(default_factory=lambda: f"ws_{uuid4().hex}")
    task_id: str
    goal: str
    mode: CognitiveMode
    active_cells: list[str] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    next_action: str | None = None


class CellResult(BaseModel):
    """Typed output from a cell."""

    cell_id: str
    task_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CognitiveEvent(BaseModel):
    """Append-only canonical event for replay and lineage."""

    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    event_type: str
    task_id: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    correlation_keys: dict[str, str] = Field(default_factory=dict)
