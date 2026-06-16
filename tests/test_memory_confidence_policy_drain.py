import pytest

from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore
from hex_cortex.memory.confidence_policy_autosaturation import MARKER_FILENAME
from hex_cortex.memory.confidence_policy_drain import run_memory_confidence_policy_drain_profile
from hex_cortex.memory.confidence_policy_telemetry import (
    MemoryConfidencePolicyTelemetryJsonlStore,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_policy_drain_dry_run_does_not_mutate_or_record_telemetry(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    telemetry_path = profile / "memory-confidence-policy-telemetry.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = run_memory_confidence_policy_drain_profile(
        profile,
        saturation_threshold=0.6,
        dry_run=True,
    )
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    records = MemoryConfidencePolicyTelemetryJsonlStore(telemetry_path).load()

    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert payload["policy_exhausted"] is False
    assert payload["blocked_reason"] == "policy_recommendations_remaining"
    assert persisted.confidence == 0.5
    assert records == []


def test_policy_drain_apply_reaches_stability_and_writes_marker(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    telemetry_path = profile / "memory-confidence-policy-telemetry.jsonl"
    marker_path = profile / MARKER_FILENAME
    memories = [
        MemoryRecord(title="first", body="body", confidence=0.5),
        MemoryRecord(title="second", body="body", confidence=0.55),
    ]
    LocalMemoryJsonlStore(memory_path).save(memories)

    payload = run_memory_confidence_policy_drain_profile(
        profile,
        max_iterations=5,
        stability_window=2,
        max_total_operations=1,
        max_total_positive_delta=0.05,
        saturation_threshold=0.6,
        dry_run=False,
    )
    persisted = LocalMemoryJsonlStore(memory_path).load()
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()
    records = MemoryConfidencePolicyTelemetryJsonlStore(telemetry_path).load()

    assert payload["policy_exhausted"] is True
    assert payload["stable"] is True
    assert payload["stability_state"] == "confidence_policy_stable"
    assert payload["marker_written"] is True
    assert marker_path.exists()
    assert len(audits) == payload["total_audit_records_written"]
    assert len(records) >= 2
    assert all(memory.confidence >= 0.6 for memory in persisted)


def test_policy_drain_blocks_when_max_iterations_are_exhausted(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memories = [
        MemoryRecord(title="first", body="body", confidence=0.5),
        MemoryRecord(title="second", body="body", confidence=0.5),
    ]
    LocalMemoryJsonlStore(memory_path).save(memories)

    payload = run_memory_confidence_policy_drain_profile(
        profile,
        max_iterations=1,
        stability_window=2,
        max_total_operations=1,
        max_total_positive_delta=0.05,
        saturation_threshold=0.6,
        dry_run=False,
    )

    assert payload["policy_exhausted"] is False
    assert payload["stable"] is False
    assert payload["blocked_reason"] == "policy_recommendations_remaining"
    assert payload["total_policy_apply_count"] == 1
    assert payload["total_telemetry_record_count"] == 0


def test_policy_drain_rejects_invalid_bounds(tmp_path) -> None:
    with pytest.raises(ValueError, match="max_iterations must be positive"):
        run_memory_confidence_policy_drain_profile(tmp_path, max_iterations=0)
    with pytest.raises(ValueError, match="stability_window must be positive"):
        run_memory_confidence_policy_drain_profile(tmp_path, stability_window=0)
