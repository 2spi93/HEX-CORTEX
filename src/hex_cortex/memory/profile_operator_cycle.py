"""Operator cycle orchestration for profile dispatch."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from hex_cortex.memory.profile_dispatch_recovery import inspect_profile_dispatch_recovery
from hex_cortex.memory.profile_next_action_dispatch import dispatch_profile_next_action

CYCLE_TRACE_FILENAME = "profile-cycle.jsonl"


class ProfileOperatorCycleReport(BaseModel):
    """One local operator cycle report."""

    cycle_type: str = "profile_operator_cycle"
    profile_path: str
    status: str
    decision: str
    next_action: str
    safety_status: str
    dispatch_status: str
    cycle_status: str
    cycle_reason: str
    cycle_id: str
    cycle_trace_count: int
    cycle_trace_path: str
    dispatch_id: str | None
    dispatch_history_count: int | None
    plan_action: str | None
    plan_command: str | None
    dispatch_result: dict[str, object]
    plan_result: dict[str, object] | None


def run_profile_operator_cycle(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Run one full local operator cycle pass."""

    dispatch_result = dispatch_profile_next_action(
        profile,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
        minimum_ready_score=minimum_ready_score,
    )
    plan_result = None
    cycle_status = "executed"
    cycle_reason = str(dispatch_result["dispatch_reason"])
    plan_action = None
    plan_command = None
    if dispatch_result["dispatch_status"] != "executed":
        plan_result = inspect_profile_dispatch_recovery(
            profile,
            policy_limit=policy_limit,
            policy_stability_window=policy_stability_window,
            minimum_ready_score=minimum_ready_score,
        )
        cycle_status = "plan_required"
        cycle_reason = str(plan_result["recovery_reason"])
        plan_action = str(plan_result["recovery_action"])
        plan_command = str(plan_result["recommended_command"])
    trace_payload = _append_cycle_trace(
        profile,
        {
            "status": str(dispatch_result["status"]),
            "decision": str(dispatch_result["decision"]),
            "next_action": str(dispatch_result["next_action"]),
            "safety_status": str(dispatch_result["safety_status"]),
            "dispatch_status": str(dispatch_result["dispatch_status"]),
            "cycle_status": cycle_status,
            "cycle_reason": cycle_reason,
            "dispatch_id": _optional_str(dispatch_result.get("dispatch_id")),
            "plan_action": plan_action,
        },
    )
    report = ProfileOperatorCycleReport(
        profile_path=str(profile),
        status=str(dispatch_result["status"]),
        decision=str(dispatch_result["decision"]),
        next_action=str(dispatch_result["next_action"]),
        safety_status=str(dispatch_result["safety_status"]),
        dispatch_status=str(dispatch_result["dispatch_status"]),
        cycle_status=cycle_status,
        cycle_reason=cycle_reason,
        cycle_id=str(trace_payload["cycle_id"]),
        cycle_trace_count=int(trace_payload["cycle_trace_count"]),
        cycle_trace_path=str(trace_payload["cycle_trace_path"]),
        dispatch_id=_optional_str(dispatch_result.get("dispatch_id")),
        dispatch_history_count=_optional_int(
            dispatch_result.get("dispatch_history_count")
        ),
        plan_action=plan_action,
        plan_command=plan_command,
        dispatch_result=dispatch_result,
        plan_result=plan_result,
    )
    return report.model_dump(mode="json")


def _append_cycle_trace(profile: Path, payload: dict[str, object]) -> dict[str, object]:
    path = profile / CYCLE_TRACE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    cycle_id = f"cycle_{uuid4().hex}"
    record = {
        "cycle_id": cycle_id,
        "created_at": datetime.now(UTC).isoformat(),
        **payload,
    }
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{record}\n")
    return {
        "cycle_id": cycle_id,
        "cycle_trace_count": len(existing) + 1,
        "cycle_trace_path": str(path),
    }


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
