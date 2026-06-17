"""Recovery guidance for blocked or skipped dispatch states."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from hex_cortex.memory.profile_dispatch_safety import inspect_profile_dispatch_safety
from hex_cortex.memory.profile_next_action import inspect_profile_next_action


class ProfileDispatchRecoveryReport(BaseModel):
    """Recovery report for dispatch preflight and dispatch blocks."""

    recovery_type: str = "profile_dispatch_recovery"
    profile_path: str
    status: str
    decision: str
    next_action: str
    safety_status: str
    allowed: bool
    safety_reasons: list[str]
    recovery_action: str
    recovery_reason: str
    recommended_command: str


def inspect_profile_dispatch_recovery(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Return the shortest recovery action for the current dispatch state."""

    next_payload = inspect_profile_next_action(
        profile,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
        minimum_ready_score=minimum_ready_score,
    )
    safety_payload = inspect_profile_dispatch_safety(profile, next_payload)
    recovery_action, recovery_reason, command = _recovery_for_state(
        profile,
        next_payload,
        safety_payload,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
        minimum_ready_score=minimum_ready_score,
    )
    report = ProfileDispatchRecoveryReport(
        profile_path=str(profile),
        status=str(next_payload["status"]),
        decision=str(next_payload["decision"]),
        next_action=str(next_payload["next_action"]),
        safety_status=str(safety_payload["safety_status"]),
        allowed=bool(safety_payload["allowed"]),
        safety_reasons=list(safety_payload["safety_reasons"]),
        recovery_action=recovery_action,
        recovery_reason=recovery_reason,
        recommended_command=command,
    )
    return report.model_dump(mode="json")


def _recovery_for_state(
    profile: Path,
    next_payload: dict[str, object],
    safety_payload: dict[str, object],
    *,
    policy_limit: int,
    policy_stability_window: int,
    minimum_ready_score: float,
) -> tuple[str, str, str]:
    if safety_payload["allowed"] is True:
        return (
            "dispatch_now",
            "dispatch_safety_allows_execution",
            _command("hexdispatch", profile, policy_limit, policy_stability_window, minimum_ready_score),
        )
    if next_payload["decision"] == "watch":
        return (
            "review_watch_reasons",
            str(next_payload["reason"]),
            _command("hexctl", profile, policy_limit, policy_stability_window, minimum_ready_score),
        )
    if next_payload["decision"] == "block":
        return (
            "repair_profile_readiness",
            str(next_payload["reason"]),
            _command("hexctl", profile, policy_limit, policy_stability_window, minimum_ready_score),
        )
    return (
        "refresh_dispatch_preflight",
        "dispatch_state_not_allowed",
        _command("hexpreflight", profile, policy_limit, policy_stability_window, minimum_ready_score),
    )


def _command(
    binary: str,
    profile: Path,
    policy_limit: int,
    policy_stability_window: int,
    minimum_ready_score: float,
) -> str:
    return (
        f"{binary} {profile} --policy-limit {policy_limit} "
        f"--policy-stability-window {policy_stability_window} "
        f"--minimum-ready-score {minimum_ready_score} --pretty"
    )
