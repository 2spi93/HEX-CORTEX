"""Operational readiness verdict for local HEX-CORTEX profiles."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.cli import inspect_profile
from hex_cortex.memory.confidence_audit_summary import summarize_memory_confidence_audit
from hex_cortex.memory.confidence_policy import run_memory_confidence_policy_profile
from hex_cortex.memory.confidence_policy_autosaturation import (
    load_memory_confidence_policy_stability_marker,
)
from hex_cortex.memory.confidence_policy_telemetry import (
    summarize_memory_confidence_policy_telemetry,
)


class ProfileOperationalReadinessVerdict(StrEnum):
    """Profile operational readiness verdicts."""

    READY = "profile_ready"
    WATCH = "profile_watch"
    BLOCKED = "profile_blocked"


class ProfileOperationalReadinessComponent(BaseModel):
    """One readiness component."""

    name: str
    status: ProfileOperationalReadinessVerdict
    reason: str
    score: float = Field(ge=0.0, le=1.0)


class ProfileOperationalReadinessReport(BaseModel):
    """Unified operational readiness report."""

    readiness_type: str = "profile_operational_readiness"
    profile_path: str
    verdict: ProfileOperationalReadinessVerdict
    score: float = Field(ge=0.0, le=1.0)
    blocked_reasons: list[str]
    watch_reasons: list[str]
    components: list[ProfileOperationalReadinessComponent]
    profile_health: dict[str, object]
    memory_confidence_audit_summary: dict[str, object]
    memory_confidence_policy_report: dict[str, object]
    memory_confidence_policy_telemetry: dict[str, object]
    memory_confidence_policy_stability_marker: dict[str, object]


def inspect_profile_operational_readiness(
    profile: Path,
    *,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
) -> dict[str, object]:
    """Inspect a profile and return one operational readiness verdict."""

    profile_payload = inspect_profile(profile)
    audit_summary = summarize_memory_confidence_audit(
        profile / "memory-confidence-audit.jsonl",
    )
    policy_report = run_memory_confidence_policy_profile(
        profile,
        limit=policy_limit,
        dry_run=True,
    )
    telemetry = summarize_memory_confidence_policy_telemetry(
        profile / "memory-confidence-policy-telemetry.jsonl",
        stability_window=policy_stability_window,
    )
    marker = load_memory_confidence_policy_stability_marker(profile)
    components = [
        _spine_component(profile_payload),
        _health_component(profile_payload),
        _policy_report_component(policy_report),
        _policy_stability_component(telemetry, marker),
        _audit_component(audit_summary),
        _pruning_component(profile_payload),
    ]
    verdict = _overall_verdict(components)
    blocked_reasons = [
        component.reason
        for component in components
        if component.status == ProfileOperationalReadinessVerdict.BLOCKED
    ]
    watch_reasons = [
        component.reason
        for component in components
        if component.status == ProfileOperationalReadinessVerdict.WATCH
    ]
    score = round(sum(component.score for component in components) / len(components), 4)
    report = ProfileOperationalReadinessReport(
        profile_path=str(profile),
        verdict=verdict,
        score=score,
        blocked_reasons=blocked_reasons,
        watch_reasons=watch_reasons,
        components=components,
        profile_health=profile_payload["profile_health"],
        memory_confidence_audit_summary=audit_summary,
        memory_confidence_policy_report=policy_report,
        memory_confidence_policy_telemetry=telemetry,
        memory_confidence_policy_stability_marker=marker,
    )
    return report.model_dump(mode="json")


def _spine_component(
    profile_payload: dict[str, object],
) -> ProfileOperationalReadinessComponent:
    spine = profile_payload["spine"]
    if not spine["exists"]:
        return _component("spine", ProfileOperationalReadinessVerdict.BLOCKED, "spine_missing", 0.0)
    if not spine["integrity_ok"]:
        return _component("spine", ProfileOperationalReadinessVerdict.BLOCKED, "spine_integrity_failed", 0.0)
    return _component("spine", ProfileOperationalReadinessVerdict.READY, "spine_integrity_ok", 1.0)


def _health_component(
    profile_payload: dict[str, object],
) -> ProfileOperationalReadinessComponent:
    health = profile_payload["profile_health"]
    if health["status"] == "blocked":
        return _component("profile_health", ProfileOperationalReadinessVerdict.BLOCKED, "profile_health_blocked", 0.0)
    if health["status"] == "watch":
        return _component("profile_health", ProfileOperationalReadinessVerdict.WATCH, "profile_health_watch", 0.7)
    return _component("profile_health", ProfileOperationalReadinessVerdict.READY, "profile_health_healthy", 1.0)


def _policy_report_component(
    policy_report: dict[str, object],
) -> ProfileOperationalReadinessComponent:
    selected = int(policy_report["selected_action_count"])
    if selected > 0:
        return _component(
            "memory_confidence_policy_report",
            ProfileOperationalReadinessVerdict.WATCH,
            "policy_recommendations_remaining",
            0.6,
        )
    return _component(
        "memory_confidence_policy_report",
        ProfileOperationalReadinessVerdict.READY,
        "policy_exhausted",
        1.0,
    )


def _policy_stability_component(
    telemetry: dict[str, object],
    marker: dict[str, object],
) -> ProfileOperationalReadinessComponent:
    if marker["exists"]:
        marker_payload = marker["marker"]
        if marker_payload["stability_state"] == "confidence_policy_stable":
            return _component(
                "memory_confidence_policy_stability",
                ProfileOperationalReadinessVerdict.READY,
                "confidence_policy_stability_marker_present",
                1.0,
            )
    if telemetry["stability_state"] == "confidence_policy_stable":
        return _component(
            "memory_confidence_policy_stability",
            ProfileOperationalReadinessVerdict.WATCH,
            "confidence_policy_stable_without_marker",
            0.8,
        )
    return _component(
        "memory_confidence_policy_stability",
        ProfileOperationalReadinessVerdict.WATCH,
        str(telemetry["stability_reason"]),
        0.6,
    )


def _audit_component(
    audit_summary: dict[str, object],
) -> ProfileOperationalReadinessComponent:
    if int(audit_summary["total_audit_count"]) == 0:
        return _component("memory_confidence_audit", ProfileOperationalReadinessVerdict.WATCH, "confidence_audit_missing", 0.5)
    if float(audit_summary["net_delta"]) < 0:
        return _component("memory_confidence_audit", ProfileOperationalReadinessVerdict.WATCH, "confidence_audit_net_negative", 0.6)
    return _component("memory_confidence_audit", ProfileOperationalReadinessVerdict.READY, "confidence_audit_net_non_negative", 1.0)


def _pruning_component(
    profile_payload: dict[str, object],
) -> ProfileOperationalReadinessComponent:
    pruning_audit = profile_payload["pruning_audit"]
    memory = profile_payload["memory"]
    if int(memory["hidden_memory_count"]) > 0:
        return _component("pruning", ProfileOperationalReadinessVerdict.WATCH, "hidden_memory_present", 0.7)
    if not pruning_audit["exists"]:
        return _component("pruning", ProfileOperationalReadinessVerdict.WATCH, "pruning_audit_missing", 0.7)
    return _component("pruning", ProfileOperationalReadinessVerdict.READY, "pruning_clean", 1.0)


def _overall_verdict(
    components: list[ProfileOperationalReadinessComponent],
) -> ProfileOperationalReadinessVerdict:
    if any(component.status == ProfileOperationalReadinessVerdict.BLOCKED for component in components):
        return ProfileOperationalReadinessVerdict.BLOCKED
    if any(component.status == ProfileOperationalReadinessVerdict.WATCH for component in components):
        return ProfileOperationalReadinessVerdict.WATCH
    return ProfileOperationalReadinessVerdict.READY


def _component(
    name: str,
    status: ProfileOperationalReadinessVerdict,
    reason: str,
    score: float,
) -> ProfileOperationalReadinessComponent:
    return ProfileOperationalReadinessComponent(
        name=name,
        status=status,
        reason=reason,
        score=score,
    )
