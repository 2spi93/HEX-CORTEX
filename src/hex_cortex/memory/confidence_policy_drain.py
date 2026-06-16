"""Drain remaining memory confidence policy recommendations safely."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.memory.confidence_policy import run_memory_confidence_policy_profile
from hex_cortex.memory.confidence_policy_autosaturation import (
    run_memory_confidence_policy_autosaturation_profile,
)
from hex_cortex.memory.confidence_policy_telemetry import (
    record_memory_confidence_policy_telemetry_profile,
    summarize_memory_confidence_policy_telemetry,
)


class MemoryConfidencePolicyDrainStep(BaseModel):
    """One step executed or previewed by the policy drain."""

    step_index: int = Field(ge=0)
    step_type: str
    selected_action_count: int = Field(ge=0)
    skipped_action_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    policy_net_delta: float
    audit_records_written: int = Field(ge=0)
    telemetry_record_count: int | None = Field(default=None, ge=0)


class MemoryConfidencePolicyDrainReport(BaseModel):
    """Report for a policy drain run."""

    drain_type: str = "memory_confidence_policy_profile"
    profile_path: str
    dry_run: bool
    applied: bool
    max_iterations: int = Field(ge=1)
    stability_window: int = Field(ge=1)
    policy_exhausted: bool
    stable: bool
    stability_state: str
    total_policy_apply_count: int = Field(ge=0)
    total_telemetry_record_count: int = Field(ge=0)
    total_audit_records_written: int = Field(ge=0)
    marker_written: bool
    blocked_reason: str | None
    final_policy_report: dict[str, object]
    final_telemetry_summary: dict[str, object]
    autosaturation_report: dict[str, object] | None
    steps: list[MemoryConfidencePolicyDrainStep]


def run_memory_confidence_policy_drain_profile(
    profile: Path,
    *,
    max_iterations: int = 10,
    stability_window: int = 3,
    max_total_positive_delta: float = 0.1,
    max_total_negative_delta: float = 0.05,
    max_total_operations: int = 2,
    limit: int = 6,
    confirmation_delta: float = 0.05,
    saturation_threshold: float = 0.7,
    min_priority_score: float = 0.0,
    recovery_amount: float = 0.02,
    recovery_ceiling: float = 0.7,
    stale_after_days: int = 30,
    decay_amount: float = 0.05,
    minimum_confidence: float = 0.3,
    write_stability_marker: bool = True,
    dry_run: bool = True,
) -> dict[str, object]:
    """Preview or drain policy recommendations until stability can be reached."""

    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    if stability_window <= 0:
        raise ValueError("stability_window must be positive")

    steps: list[MemoryConfidencePolicyDrainStep] = []
    if dry_run:
        final_policy_report = _policy_report(
            profile,
            limit=limit,
            max_total_positive_delta=max_total_positive_delta,
            max_total_negative_delta=max_total_negative_delta,
            max_total_operations=max_total_operations,
            confirmation_delta=confirmation_delta,
            saturation_threshold=saturation_threshold,
            min_priority_score=min_priority_score,
            recovery_amount=recovery_amount,
            recovery_ceiling=recovery_ceiling,
            stale_after_days=stale_after_days,
            decay_amount=decay_amount,
            minimum_confidence=minimum_confidence,
            dry_run=True,
        )
        final_telemetry_summary = _telemetry_summary(profile, stability_window)
        return _drain_report(
            profile,
            dry_run=True,
            max_iterations=max_iterations,
            stability_window=stability_window,
            final_policy_report=final_policy_report,
            final_telemetry_summary=final_telemetry_summary,
            steps=steps,
            total_policy_apply_count=0,
            total_telemetry_record_count=0,
            total_audit_records_written=0,
            autosaturation_report=None,
        )

    total_audit_records_written = 0
    for iteration in range(max_iterations):
        preview = _policy_report(
            profile,
            limit=limit,
            max_total_positive_delta=max_total_positive_delta,
            max_total_negative_delta=max_total_negative_delta,
            max_total_operations=max_total_operations,
            confirmation_delta=confirmation_delta,
            saturation_threshold=saturation_threshold,
            min_priority_score=min_priority_score,
            recovery_amount=recovery_amount,
            recovery_ceiling=recovery_ceiling,
            stale_after_days=stale_after_days,
            decay_amount=decay_amount,
            minimum_confidence=minimum_confidence,
            dry_run=True,
        )
        if int(preview["selected_action_count"]) == 0:
            break
        applied = _policy_report(
            profile,
            limit=limit,
            max_total_positive_delta=max_total_positive_delta,
            max_total_negative_delta=max_total_negative_delta,
            max_total_operations=max_total_operations,
            confirmation_delta=confirmation_delta,
            saturation_threshold=saturation_threshold,
            min_priority_score=min_priority_score,
            recovery_amount=recovery_amount,
            recovery_ceiling=recovery_ceiling,
            stale_after_days=stale_after_days,
            decay_amount=decay_amount,
            minimum_confidence=minimum_confidence,
            dry_run=False,
        )
        total_audit_records_written += int(applied["audit_records_written"])
        steps.append(_step_from_policy_report(iteration, applied))

    final_policy_report = _policy_report(
        profile,
        limit=limit,
        max_total_positive_delta=max_total_positive_delta,
        max_total_negative_delta=max_total_negative_delta,
        max_total_operations=max_total_operations,
        confirmation_delta=confirmation_delta,
        saturation_threshold=saturation_threshold,
        min_priority_score=min_priority_score,
        recovery_amount=recovery_amount,
        recovery_ceiling=recovery_ceiling,
        stale_after_days=stale_after_days,
        decay_amount=decay_amount,
        minimum_confidence=minimum_confidence,
        dry_run=True,
    )
    telemetry_record_count = 0
    final_telemetry_summary = _telemetry_summary(profile, stability_window)
    while (
        int(final_policy_report["selected_action_count"]) == 0
        and final_telemetry_summary["stability_state"] != "confidence_policy_stable"
    ):
        telemetry_payload = record_memory_confidence_policy_telemetry_profile(
            profile,
            limit=limit,
            max_total_positive_delta=max_total_positive_delta,
            max_total_negative_delta=max_total_negative_delta,
            max_total_operations=max_total_operations,
            confirmation_delta=confirmation_delta,
            saturation_threshold=saturation_threshold,
            min_priority_score=min_priority_score,
            recovery_amount=recovery_amount,
            recovery_ceiling=recovery_ceiling,
            stale_after_days=stale_after_days,
            decay_amount=decay_amount,
            minimum_confidence=minimum_confidence,
        )
        telemetry_record_count += 1
        telemetry_record = telemetry_payload["telemetry_record"]
        steps.append(_step_from_telemetry_record(len(steps), telemetry_record, telemetry_payload))
        final_telemetry_summary = _telemetry_summary(profile, stability_window)

    autosaturation_report = None
    if write_stability_marker and final_telemetry_summary["stability_state"] == "confidence_policy_stable":
        autosaturation_report = run_memory_confidence_policy_autosaturation_profile(
            profile,
            stability_window=stability_window,
            dry_run=False,
        )

    return _drain_report(
        profile,
        dry_run=False,
        max_iterations=max_iterations,
        stability_window=stability_window,
        final_policy_report=final_policy_report,
        final_telemetry_summary=final_telemetry_summary,
        steps=steps,
        total_policy_apply_count=sum(1 for step in steps if step.step_type == "policy_apply"),
        total_telemetry_record_count=telemetry_record_count,
        total_audit_records_written=total_audit_records_written,
        autosaturation_report=autosaturation_report,
    )


def _policy_report(profile: Path, **kwargs: object) -> dict[str, object]:
    return run_memory_confidence_policy_profile(profile, **kwargs)


def _telemetry_summary(profile: Path, stability_window: int) -> dict[str, object]:
    return summarize_memory_confidence_policy_telemetry(
        profile / "memory-confidence-policy-telemetry.jsonl",
        stability_window=stability_window,
    )


def _step_from_policy_report(
    step_index: int,
    policy_report: dict[str, object],
) -> MemoryConfidencePolicyDrainStep:
    return MemoryConfidencePolicyDrainStep(
        step_index=step_index,
        step_type="policy_apply",
        selected_action_count=int(policy_report["selected_action_count"]),
        skipped_action_count=int(policy_report["skipped_action_count"]),
        candidate_count=int(policy_report["candidate_count"]),
        policy_net_delta=float(policy_report["net_delta"]),
        audit_records_written=int(policy_report["audit_records_written"]),
    )


def _step_from_telemetry_record(
    step_index: int,
    telemetry_record: dict[str, object],
    telemetry_payload: dict[str, object],
) -> MemoryConfidencePolicyDrainStep:
    return MemoryConfidencePolicyDrainStep(
        step_index=step_index,
        step_type="telemetry_record",
        selected_action_count=int(telemetry_record["selected_action_count"]),
        skipped_action_count=int(telemetry_record["skipped_action_count"]),
        candidate_count=int(telemetry_record["candidate_count"]),
        policy_net_delta=float(telemetry_record["policy_net_delta"]),
        audit_records_written=0,
        telemetry_record_count=int(telemetry_payload["telemetry_record_count"]),
    )


def _drain_report(
    profile: Path,
    *,
    dry_run: bool,
    max_iterations: int,
    stability_window: int,
    final_policy_report: dict[str, object],
    final_telemetry_summary: dict[str, object],
    steps: list[MemoryConfidencePolicyDrainStep],
    total_policy_apply_count: int,
    total_telemetry_record_count: int,
    total_audit_records_written: int,
    autosaturation_report: dict[str, object] | None,
) -> dict[str, object]:
    policy_exhausted = int(final_policy_report["selected_action_count"]) == 0
    stable = final_telemetry_summary["stability_state"] == "confidence_policy_stable"
    marker_written = bool(autosaturation_report and autosaturation_report["marker_written"])
    blocked_reason = None
    if not policy_exhausted:
        blocked_reason = "policy_recommendations_remaining"
    elif not stable:
        blocked_reason = str(final_telemetry_summary["stability_reason"])
    report = MemoryConfidencePolicyDrainReport(
        profile_path=str(profile),
        dry_run=dry_run,
        applied=not dry_run,
        max_iterations=max_iterations,
        stability_window=stability_window,
        policy_exhausted=policy_exhausted,
        stable=stable,
        stability_state=str(final_telemetry_summary["stability_state"]),
        total_policy_apply_count=total_policy_apply_count,
        total_telemetry_record_count=total_telemetry_record_count,
        total_audit_records_written=total_audit_records_written,
        marker_written=marker_written,
        blocked_reason=blocked_reason,
        final_policy_report=final_policy_report,
        final_telemetry_summary=final_telemetry_summary,
        autosaturation_report=autosaturation_report,
        steps=steps,
    )
    return report.model_dump(mode="json")
