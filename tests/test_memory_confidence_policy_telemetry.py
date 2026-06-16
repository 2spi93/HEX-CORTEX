import pytest

from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore
from hex_cortex.memory.confidence_policy_telemetry import (
    MemoryConfidencePolicyTelemetryJsonlStore,
    record_memory_confidence_policy_telemetry_profile,
    summarize_memory_confidence_policy_telemetry,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_policy_telemetry_records_dry_run_without_mutation(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    telemetry_path = profile / "memory-confidence-policy-telemetry.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = record_memory_confidence_policy_telemetry_profile(
        profile,
        limit=1,
        max_total_positive_delta=0.05,
    )
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()
    records = MemoryConfidencePolicyTelemetryJsonlStore(telemetry_path).load()

    assert payload["record_type"] == "memory_confidence_policy_telemetry"
    assert payload["telemetry_record_count"] == 1
    assert persisted.confidence == 0.5
    assert audits == []
    assert len(records) == 1
    assert records[0].policy_report["dry_run"] is True
    assert records[0].policy_report["applied"] is False
    assert records[0].selected_action_count == 1
    assert records[0].policy_net_delta == 0.05


def test_policy_telemetry_summary_handles_missing_and_existing_records(tmp_path) -> None:
    telemetry_path = tmp_path / "policy-telemetry.jsonl"

    missing = summarize_memory_confidence_policy_telemetry(telemetry_path)
    assert missing["exists"] is False
    assert missing["total_record_count"] == 0
    assert missing["stability_state"] == "confidence_policy_insufficient_history"

    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.8, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([memory])
    record_memory_confidence_policy_telemetry_profile(profile)

    summary = summarize_memory_confidence_policy_telemetry(
        profile / "memory-confidence-policy-telemetry.jsonl",
    )
    assert summary["exists"] is True
    assert summary["total_record_count"] == 1
    assert summary["latest_selected_action_count"] == 0
    assert summary["stable_zero_action_count"] == 1
    assert summary["consecutive_zero_action_count"] == 1
    assert summary["stability_window"] == 3
    assert summary["stability_state"] == "confidence_policy_insufficient_history"


def test_policy_telemetry_summary_marks_stable_after_consecutive_zero_window(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.8, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([memory])

    for _ in range(3):
        record_memory_confidence_policy_telemetry_profile(profile)

    summary = summarize_memory_confidence_policy_telemetry(
        profile / "memory-confidence-policy-telemetry.jsonl",
        stability_window=3,
    )

    assert summary["total_record_count"] == 3
    assert summary["consecutive_zero_action_count"] == 3
    assert summary["stability_state"] == "confidence_policy_stable"
    assert summary["stability_reason"] == "consecutive_zero_action_window_reached"


def test_policy_telemetry_summary_marks_active_when_latest_records_recommend_actions(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    active_memory = MemoryRecord(title="active", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([active_memory])

    for _ in range(3):
        record_memory_confidence_policy_telemetry_profile(profile)

    summary = summarize_memory_confidence_policy_telemetry(
        profile / "memory-confidence-policy-telemetry.jsonl",
        stability_window=3,
    )

    assert summary["total_record_count"] == 3
    assert summary["consecutive_zero_action_count"] == 0
    assert summary["stability_state"] == "confidence_policy_active"
    assert summary["stability_reason"] == "policy_still_recommends_actions"


def test_policy_telemetry_summary_rejects_invalid_stability_window(tmp_path) -> None:
    with pytest.raises(ValueError, match="stability_window must be positive"):
        summarize_memory_confidence_policy_telemetry(tmp_path / "telemetry.jsonl", stability_window=0)
