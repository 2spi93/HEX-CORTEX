"""Autosaturation marker for stable memory confidence policy telemetry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.memory.confidence_policy_telemetry import (
    MemoryConfidencePolicyStabilityState,
    summarize_memory_confidence_policy_telemetry,
)

MARKER_FILENAME = "memory-confidence-policy-stability.json"
TELEMETRY_FILENAME = "memory-confidence-policy-telemetry.jsonl"


class MemoryConfidencePolicyStabilityMarker(BaseModel):
    """Local marker proving confidence policy stability was reached."""

    marker_type: str = "memory_confidence_policy_stability"
    marker_version: str = "1.0"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    stability_state: MemoryConfidencePolicyStabilityState
    stability_reason: str
    stability_window: int = Field(ge=1)
    consecutive_zero_action_count: int = Field(ge=0)
    total_telemetry_record_count: int = Field(ge=0)
    latest_telemetry_id: str | None
    latest_policy_net_delta: float | None
    latest_selected_action_count: int | None
    source_telemetry_path: str


def run_memory_confidence_policy_autosaturation_profile(
    profile: Path,
    *,
    stability_window: int = 3,
    dry_run: bool = True,
    clear_stale_marker: bool = True,
) -> dict[str, object]:
    """Preview or write a local confidence policy stability marker."""

    marker_path = profile / MARKER_FILENAME
    telemetry_path = profile / TELEMETRY_FILENAME
    summary = summarize_memory_confidence_policy_telemetry(
        telemetry_path,
        stability_window=stability_window,
    )
    eligible = summary["stability_state"] == MemoryConfidencePolicyStabilityState.STABLE.value
    marker = _marker_from_summary(profile, marker_path, telemetry_path, summary)
    stale_marker_cleared = False
    if not dry_run and eligible:
        _write_marker(marker_path, marker)
    elif not dry_run and clear_stale_marker and marker_path.exists():
        marker_path.unlink()
        stale_marker_cleared = True

    marker_exists_after = marker_path.exists()
    return {
        "autosaturation_type": "memory_confidence_policy_profile",
        "profile_path": str(profile),
        "telemetry_path": str(telemetry_path),
        "marker_path": str(marker_path),
        "dry_run": dry_run,
        "applied": not dry_run,
        "eligible": eligible,
        "marker_written": bool(not dry_run and eligible),
        "stale_marker_cleared": stale_marker_cleared,
        "marker_exists_after": marker_exists_after,
        "blocked_reason": None if eligible else summary["stability_reason"],
        "stability_summary": summary,
        "marker_preview": marker.model_dump(mode="json"),
    }


def load_memory_confidence_policy_stability_marker(profile: Path) -> dict[str, object]:
    """Load a local stability marker if present."""

    marker_path = profile / MARKER_FILENAME
    if not marker_path.exists():
        return {
            "inspect_type": "memory_confidence_policy_stability_marker",
            "path": str(marker_path),
            "exists": False,
            "marker": None,
        }
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    marker = MemoryConfidencePolicyStabilityMarker.model_validate(payload)
    return {
        "inspect_type": "memory_confidence_policy_stability_marker",
        "path": str(marker_path),
        "exists": True,
        "marker": marker.model_dump(mode="json"),
    }


def _marker_from_summary(
    profile: Path,
    marker_path: Path,
    telemetry_path: Path,
    summary: dict[str, object],
) -> MemoryConfidencePolicyStabilityMarker:
    return MemoryConfidencePolicyStabilityMarker(
        profile_path=str(profile),
        stability_state=MemoryConfidencePolicyStabilityState(summary["stability_state"]),
        stability_reason=str(summary["stability_reason"]),
        stability_window=int(summary["stability_window"]),
        consecutive_zero_action_count=int(summary["consecutive_zero_action_count"]),
        total_telemetry_record_count=int(summary["total_record_count"]),
        latest_telemetry_id=summary["latest_telemetry_id"],
        latest_policy_net_delta=summary["latest_policy_net_delta"],
        latest_selected_action_count=summary["latest_selected_action_count"],
        source_telemetry_path=str(telemetry_path),
    )


def _write_marker(
    marker_path: Path,
    marker: MemoryConfidencePolicyStabilityMarker,
) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(marker.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
