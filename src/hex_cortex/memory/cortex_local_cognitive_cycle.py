"""Adapter between the existing CognitiveClock and new bounded local Harness.

Runs real typed ticks and writes redacted lifecycle events to CanonicalSpine.
Raw task prompts and model outputs never enter tick payloads or event receipts.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from hex_cortex.core.cognitive_clock import (
    CognitiveClock,
    RegisteredTick,
    TickName,
    TickResult,
    TickStatus,
)
from hex_cortex.core.schemas import CognitiveMode, Task as CoreTask
from hex_cortex.memory.cortex_local_harness_v2 import LocalHarness, Task


def run_clocked_local_task(
    harness: LocalHarness,
    task: Task,
    *,
    models: list[str] | None = None,
    brain: Callable[[str, Task], str] | None = None,
    approved: bool = False,
    max_latency_ms: int = 120_000,
) -> dict[str, object]:
    """Finite cognitive cycle, with no external scheduling or implicit rights."""
    goal_hash = hashlib.sha256(task.instruction.encode("utf-8")).hexdigest()
    core_task = CoreTask(
        task_id=task.task_id,
        content="sha256:" + goal_hash,
        domain_hints=[task.domain],
        latency_budget_ms=max_latency_ms,
    )
    actual_result: dict[str, object] = {}

    def _intake(_context) -> dict[str, object]:
        return {"project": harness.session.project_id, "goal_sha256": goal_hash}

    def _route(_context) -> dict[str, object]:
        return {"candidate_count": len(models or []), "model_requested": brain is not None,
                "explicit_approval": approved}

    def _action(_context) -> TickResult:
        executed = harness.execute(
            task, models=models, brain=brain, approved=approved,
        )
        actual_result.update(executed)
        receipt = executed["receipt"]
        assert isinstance(receipt, dict)
        return TickResult(
            tick_name=TickName.ACTION,
            status=TickStatus.SUCCESS if executed["status"] == "complete" else TickStatus.FAILED,
            payload={"receipt_sha256": receipt["sha256"], "status": executed["status"]},
            error=str(executed["reason"]) if executed["status"] != "complete" else None,
        )

    def _critic(_context) -> TickResult:
        if actual_result.get("status") != "complete":
            return TickResult(
                tick_name=TickName.CRITIC, status=TickStatus.FAILED,
                error="action_did_not_complete",
            )
        if brain is not None and not actual_result.get("output"):
            return TickResult(
                tick_name=TickName.CRITIC, status=TickStatus.FAILED,
                error="empty_model_answer",
            )
        return TickResult(
            tick_name=TickName.CRITIC, status=TickStatus.SUCCESS,
            payload={"output_present": bool(actual_result.get("output")),
                     "receipt_verified": harness.verify_replay()},
        )

    def _verify(_context) -> TickResult:
        integrity = harness.verify_replay()
        return TickResult(
            tick_name=TickName.SPINE_VERIFY,
            status=TickStatus.SUCCESS if integrity else TickStatus.FAILED,
            payload={"integrity_ok": integrity},
            error=None if integrity else "canonical_chain_invalid",
        )

    clock = CognitiveClock(
        spine=harness.spine, max_ticks=5, max_latency_ms=max_latency_ms,
    )
    clock_report = clock.run(
        task=core_task,
        mode=CognitiveMode.WORKING,
        ticks=[
            RegisteredTick(TickName.INTAKE, _intake),
            RegisteredTick(TickName.ROUTING, _route),
            RegisteredTick(TickName.ACTION, _action),
            RegisteredTick(TickName.CRITIC, _critic),
            RegisteredTick(TickName.SPINE_VERIFY, _verify),
        ],
    )
    result = dict(actual_result)
    if not result:
        result = {"status": "blocked", "reason": clock_report.stopped_reason,
                  "output": None, "tool_result": None, "receipt": None}
    result["clock_completed"] = clock_report.completed
    result["tick_statuses"] = [
        {"name": row.tick_name.value, "status": row.status.value}
        for row in clock_report.results
    ]
    result["canonical_spine_verified"] = harness.spine.verify_integrity().ok
    result["canonical_spine_event_count"] = len(harness.spine.events)
    return result
