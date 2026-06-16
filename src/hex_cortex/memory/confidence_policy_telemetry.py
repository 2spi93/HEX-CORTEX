"""Telemetry for dry-run memory confidence policy reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.confidence_policy import run_memory_confidence_policy_profile


class MemoryConfidencePolicyStabilityState(StrEnum):
    """Stability state inferred from policy telemetry."""

    STABLE = "confidence_policy_stable"
    ACTIVE = "confidence_policy_active"
    INSUFFICIENT_HISTORY = "confidence_policy_insufficient_history"


class MemoryConfidencePolicyTelemetryRecord(BaseModel):
    """One telemetry record for a dry-run policy report."""

    telemetry_id: str = Field(default_factory=lambda: f"policytel_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_action_count: int = Field(ge=0)
    skipped_action_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    policy_net_delta: float
    total_positive_delta: float
    total_negative_delta: float
    policy_report: dict[str, object]


class MemoryConfidencePolicyTelemetrySummary(BaseModel):
    """Summary of policy telemetry records."""

    inspect_type: str = "memory_confidence_policy_telemetry"
    path: str
    exists: bool
    total_record_count: int = Field(ge=0)
    latest_telemetry_id: str | None
    latest_policy_net_delta: float | None
    latest_selected_action_count: int | None
    latest_skipped_action_count: int | None
    latest_candidate_count: int | None
    stable_zero_action_count: int = Field(ge=0)
    consecutive_zero_action_count: int = Field(ge=0)
    stability_window: int = Field(ge=1)
    stability_state: MemoryConfidencePolicyStabilityState
    stability_reason: str


class MemoryConfidencePolicyTelemetryJsonlStore:
    """Persist policy telemetry records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[MemoryConfidencePolicyTelemetryRecord]:
        """Load telemetry records."""

        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    records.append(
                        MemoryConfidencePolicyTelemetryRecord.model_validate(payload)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid memory confidence policy telemetry at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[MemoryConfidencePolicyTelemetryRecord]) -> int:
        """Replace JSONL content with telemetry records."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: MemoryConfidencePolicyTelemetryRecord) -> int:
        """Append one telemetry record and return the new count."""

        records = self.load()
        records.append(record)
        return self.save(records)


def record_memory_confidence_policy_telemetry_profile(
    profile: Path,
    *,
    limit: int = 5,
    max_total_positive_delta: float = 0.1,
    max_total_negative_delta: float = 0.05,
    max_total_operations: int = 5,
    confirmation_delta: float = 0.05,
    saturation_threshold: float = 0.7,
    min_priority_score: float = 0.0,
    recovery_amount: float = 0.02,
    recovery_ceiling: float = 0.7,
    stale_after_days: int = 30,
    decay_amount: float = 0.05,
    minimum_confidence: float = 0.3,
) -> dict[str, object]:
    """Record a dry-run policy report in telemetry JSONL."""

    telemetry_path = profile / "memory-confidence-policy-telemetry.jsonl"
    policy_report = run_memory_confidence_policy_profile(
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
    record = MemoryConfidencePolicyTelemetryRecord(
        profile_path=str(profile),
        selected_action_count=int(policy_report["selected_action_count"]),
        skipped_action_count=int(policy_report["skipped_action_count"]),
        candidate_count=int(policy_report["candidate_count"]),
        policy_net_delta=float(policy_report["net_delta"]),
        total_positive_delta=float(policy_report["total_positive_delta"]),
        total_negative_delta=float(policy_report["total_negative_delta"]),
        policy_report=policy_report,
    )
    store = MemoryConfidencePolicyTelemetryJsonlStore(telemetry_path)
    record_count = store.append(record)
    return {
        "record_type": "memory_confidence_policy_telemetry",
        "profile_path": str(profile),
        "telemetry_path": str(telemetry_path),
        "telemetry_record_count": record_count,
        "telemetry_record": record.model_dump(mode="json"),
    }


def summarize_memory_confidence_policy_telemetry(
    path: Path,
    *,
    stability_window: int = 3,
) -> dict[str, object]:
    """Summarize policy telemetry records and infer stability."""

    if stability_window <= 0:
        raise ValueError("stability_window must be positive")

    records = MemoryConfidencePolicyTelemetryJsonlStore(path).load()
    latest = records[-1] if records else None
    consecutive_zero_action_count = _consecutive_zero_action_count(records)
    stability_state, stability_reason = _stability_state(
        records,
        consecutive_zero_action_count=consecutive_zero_action_count,
        stability_window=stability_window,
    )
    summary = MemoryConfidencePolicyTelemetrySummary(
        path=str(path),
        exists=path.exists(),
        total_record_count=len(records),
        latest_telemetry_id=latest.telemetry_id if latest else None,
        latest_policy_net_delta=latest.policy_net_delta if latest else None,
        latest_selected_action_count=latest.selected_action_count if latest else None,
        latest_skipped_action_count=latest.skipped_action_count if latest else None,
        latest_candidate_count=latest.candidate_count if latest else None,
        stable_zero_action_count=sum(
            1 for record in records if record.selected_action_count == 0
        ),
        consecutive_zero_action_count=consecutive_zero_action_count,
        stability_window=stability_window,
        stability_state=stability_state,
        stability_reason=stability_reason,
    )
    return summary.model_dump(mode="json")


def _consecutive_zero_action_count(
    records: list[MemoryConfidencePolicyTelemetryRecord],
) -> int:
    count = 0
    for record in reversed(records):
        if record.selected_action_count != 0:
            break
        count += 1
    return count


def _stability_state(
    records: list[MemoryConfidencePolicyTelemetryRecord],
    *,
    consecutive_zero_action_count: int,
    stability_window: int,
) -> tuple[MemoryConfidencePolicyStabilityState, str]:
    if len(records) < stability_window:
        return (
            MemoryConfidencePolicyStabilityState.INSUFFICIENT_HISTORY,
            "not_enough_policy_telemetry_records",
        )
    if consecutive_zero_action_count >= stability_window:
        return (
            MemoryConfidencePolicyStabilityState.STABLE,
            "consecutive_zero_action_window_reached",
        )
    return (
        MemoryConfidencePolicyStabilityState.ACTIVE,
        "policy_still_recommends_actions",
    )
