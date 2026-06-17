"""Build public cognitive traces from operator cycle payloads."""

from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cognitive_trace import (
    CognitiveTraceRecord,
    CognitiveTraceStep,
    record_cognitive_trace,
)
from hex_cortex.memory.profile_operator_cycle import run_profile_operator_cycle


def build_cognitive_trace_from_cycle(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Run an operator cycle and persist a compact multi-step trace."""

    cycle = run_profile_operator_cycle(
        profile,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
        minimum_ready_score=minimum_ready_score,
    )
    trace = CognitiveTraceRecord(
        profile_path=str(profile),
        source_type=str(cycle["cycle_type"]),
        status=str(cycle["status"]),
        decision=str(cycle["decision"]),
        final_action=_final_action(cycle),
        final_reason=str(cycle["cycle_reason"]),
        steps=_steps_from_cycle(cycle),
    )
    payload = record_cognitive_trace(profile, trace)
    return {
        "trace_type": "cognitive_trace_build",
        "profile_path": str(profile),
        "cycle_status": cycle["cycle_status"],
        "dispatch_status": cycle["dispatch_status"],
        "final_action": trace.final_action,
        "trace_path": payload["trace_path"],
        "trace_count": payload["trace_count"],
        "trace_record": payload["trace_record"],
    }


def _steps_from_cycle(cycle: dict[str, object]) -> list[CognitiveTraceStep]:
    return [
        CognitiveTraceStep(
            index=0,
            label="readiness",
            observation=f"status={cycle['status']}; decision={cycle['decision']}",
            decision=str(cycle["decision"]),
            confidence=_confidence_from_status(str(cycle["status"])),
        ),
        CognitiveTraceStep(
            index=1,
            label="next_action",
            observation=f"next_action={cycle['next_action']}",
            decision=str(cycle["next_action"]),
            confidence=0.8,
        ),
        CognitiveTraceStep(
            index=2,
            label="safety",
            observation=f"safety_status={cycle['safety_status']}",
            decision=str(cycle["safety_status"]),
            confidence=0.9,
        ),
        CognitiveTraceStep(
            index=3,
            label="dispatch",
            observation=f"dispatch_status={cycle['dispatch_status']}",
            decision=str(cycle["dispatch_status"]),
            confidence=0.9,
        ),
        CognitiveTraceStep(
            index=4,
            label="cycle",
            observation=f"cycle_status={cycle['cycle_status']}",
            decision=_final_action(cycle),
            confidence=0.85,
        ),
    ]


def _final_action(cycle: dict[str, object]) -> str:
    if cycle["cycle_status"] == "executed":
        return "observe_pipeline_result"
    plan_action = cycle.get("plan_action")
    return str(plan_action) if plan_action else "inspect_operator_state"


def _confidence_from_status(status: str) -> float:
    if status == "ready":
        return 1.0
    if status == "watch":
        return 0.6
    return 0.3
