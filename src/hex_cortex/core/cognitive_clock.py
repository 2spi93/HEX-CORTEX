"""Bounded cognitive clock for HEX-CORTEX.

The clock orchestrates deterministic ticks and writes their lifecycle into the
CanonicalSpine. It is the first safe execution loop for the cortex.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from hex_cortex.core.schemas import CognitiveMode, Task
from hex_cortex.spine.canonical_spine import CanonicalSpine


class TickName(StrEnum):
    """Standard cognitive ticks."""

    INTAKE = "intake"
    RETRIEVAL = "retrieval"
    ROUTING = "routing"
    WORKSPACE = "workspace"
    PREDICTION = "prediction"
    CRITIC = "critic"
    ACTION = "action"
    COMPRESSION = "compression"
    SPINE_VERIFY = "spine_verify"


class TickStatus(StrEnum):
    """Execution status for one tick."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


class TickResult(BaseModel):
    """Result returned by a cognitive tick."""

    tick_name: TickName
    status: TickStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    error: str | None = None
    elapsed_ms: float = Field(default=0.0, ge=0.0)


class CognitiveClockReport(BaseModel):
    """Final execution report for a cognitive clock run."""

    task_id: str
    mode: CognitiveMode
    completed: bool
    results: list[TickResult] = Field(default_factory=list)
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    stopped_reason: str | None = None


@dataclass
class CognitiveTickContext:
    """Mutable execution context shared by ticks during one clock run."""

    task: Task
    mode: CognitiveMode
    spine: CanonicalSpine
    state: dict[str, Any] = field(default_factory=dict)


TickHandler = Callable[[CognitiveTickContext], TickResult | dict[str, Any] | None]


@dataclass(frozen=True)
class RegisteredTick:
    """A named tick handler registered in the cognitive clock."""

    name: TickName
    handler: TickHandler
    required: bool = True


class CognitiveClock:
    """Bounded tick runner for HEX-CORTEX.

    It records each tick start/end into the canonical spine and stops on required
    tick failure by default.
    """

    def __init__(
        self,
        *,
        spine: CanonicalSpine | None = None,
        max_ticks: int = 8,
        max_latency_ms: int = 10_000,
        stop_on_failure: bool = True,
    ) -> None:
        if max_ticks < 1:
            raise ValueError("max_ticks must be >= 1")
        if max_latency_ms < 1:
            raise ValueError("max_latency_ms must be >= 1")

        self.spine = spine or CanonicalSpine()
        self.max_ticks = max_ticks
        self.max_latency_ms = max_latency_ms
        self.stop_on_failure = stop_on_failure

    def run(
        self,
        *,
        task: Task,
        mode: CognitiveMode,
        ticks: list[RegisteredTick],
    ) -> CognitiveClockReport:
        if not ticks:
            raise ValueError("cannot run cognitive clock without ticks")
        if len(ticks) > self.max_ticks:
            raise ValueError("registered ticks exceed max_ticks")

        started_at = perf_counter()
        context = CognitiveTickContext(task=task, mode=mode, spine=self.spine)
        results: list[TickResult] = []
        stopped_reason: str | None = None

        self.spine.append(
            event_type="clock.started",
            task_id=task.task_id,
            source="CognitiveClock",
            payload={"mode": mode.value, "tick_count": len(ticks)},
        )

        for tick in ticks:
            elapsed_total_ms = self._elapsed_ms(started_at)
            if elapsed_total_ms > self.max_latency_ms:
                stopped_reason = "latency_budget_exceeded"
                break

            self.spine.append(
                event_type="tick.started",
                task_id=task.task_id,
                source="CognitiveClock",
                payload={"tick": tick.name.value, "required": tick.required},
            )

            result = self._run_tick(tick, context)
            results.append(result)
            context.state[f"tick.{tick.name.value}"] = result.model_dump(mode="json")

            self.spine.append(
                event_type="tick.completed",
                task_id=task.task_id,
                source="CognitiveClock",
                payload={
                    "tick": result.tick_name.value,
                    "status": result.status.value,
                    "payload": result.payload,
                    "error": result.error,
                    "elapsed_ms": result.elapsed_ms,
                },
                confidence=result.confidence,
            )

            if result.status == TickStatus.FAILED and tick.required and self.stop_on_failure:
                stopped_reason = f"required_tick_failed:{tick.name.value}"
                break

        completed = stopped_reason is None
        report = CognitiveClockReport(
            task_id=task.task_id,
            mode=mode,
            completed=completed,
            results=results,
            elapsed_ms=self._elapsed_ms(started_at),
            stopped_reason=stopped_reason,
        )

        self.spine.append(
            event_type="clock.completed",
            task_id=task.task_id,
            source="CognitiveClock",
            payload={
                "completed": report.completed,
                "stopped_reason": report.stopped_reason,
                "elapsed_ms": report.elapsed_ms,
                "result_count": len(report.results),
            },
        )
        return report

    def _run_tick(self, tick: RegisteredTick, context: CognitiveTickContext) -> TickResult:
        started_at = perf_counter()
        try:
            raw_result = tick.handler(context)
            elapsed_ms = self._elapsed_ms(started_at)

            if isinstance(raw_result, TickResult):
                return raw_result.model_copy(update={"elapsed_ms": elapsed_ms})

            if raw_result is None:
                return TickResult(
                    tick_name=tick.name,
                    status=TickStatus.SUCCESS,
                    payload={},
                    elapsed_ms=elapsed_ms,
                )

            return TickResult(
                tick_name=tick.name,
                status=TickStatus.SUCCESS,
                payload=raw_result,
                elapsed_ms=elapsed_ms,
            )
        except Exception as exc:  # noqa: BLE001 - tick failures must be captured as data.
            return TickResult(
                tick_name=tick.name,
                status=TickStatus.FAILED,
                error=str(exc),
                elapsed_ms=self._elapsed_ms(started_at),
            )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return (perf_counter() - started_at) * 1000
