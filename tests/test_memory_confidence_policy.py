from datetime import UTC, datetime, timedelta

from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
)
from hex_cortex.memory.confidence_policy import run_memory_confidence_policy_profile
from hex_cortex.memory.confidence_recovery import RECOVERY_REASON
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def stale_timestamp() -> str:
    return (datetime.now(UTC) - timedelta(days=60)).isoformat()


def decay_audit(memory_id: str) -> MemoryConfidenceAuditRecord:
    return MemoryConfidenceAuditRecord(
        memory_id=memory_id,
        reason="stale_memory_confidence_decay",
        before_confidence=0.6,
        after_confidence=0.59,
        delta=-0.01,
        changed=True,
        before_access_count=2,
        after_access_count=2,
    )


def test_memory_confidence_policy_dry_run_does_not_mutate(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = run_memory_confidence_policy_profile(profile, dry_run=True)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]

    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert payload["selected_action_count"] == 1
    assert payload["audit_records_written"] == 0
    assert payload["actions"][0]["action_type"] == "confirmation"
    assert persisted.confidence == 0.5


def test_memory_confidence_policy_apply_writes_selected_actions(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = run_memory_confidence_policy_profile(profile, dry_run=False)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert payload["applied"] is True
    assert payload["audit_records_written"] == 1
    assert persisted.confidence == 0.55
    assert persisted.access_count == 1
    assert audits[-1].reason == "policy_retrieval_confirmed"


def test_memory_confidence_policy_prioritizes_recovery_over_confirmation(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.59, access_count=2)
    LocalMemoryJsonlStore(memory_path).save([memory])
    MemoryConfidenceAuditJsonlStore(audit_path).save([decay_audit(memory.memory_id)])

    payload = run_memory_confidence_policy_profile(profile, dry_run=True)

    assert payload["candidate_count"] == 1
    assert payload["selected_action_count"] == 1
    assert payload["actions"][0]["action_type"] == "recovery"
    assert payload["actions"][0]["reason"] == RECOVERY_REASON


def test_memory_confidence_policy_uses_decay_after_other_actions(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    stale = MemoryRecord(
        title="stale",
        body="body",
        confidence=0.8,
        access_count=2,
        last_accessed_at=stale_timestamp(),
    )
    LocalMemoryJsonlStore(memory_path).save([stale])

    payload = run_memory_confidence_policy_profile(
        profile,
        dry_run=True,
        stale_after_days=30,
    )

    assert payload["selected_action_count"] == 1
    assert payload["actions"][0]["action_type"] == "decay"
    assert payload["actions"][0]["delta"] == -0.05


def test_memory_confidence_policy_respects_global_positive_delta_limit(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    first = MemoryRecord(title="first", body="body", confidence=0.5)
    second = MemoryRecord(title="second", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([first, second])

    payload = run_memory_confidence_policy_profile(
        profile,
        dry_run=True,
        limit=2,
        max_total_positive_delta=0.05,
    )

    assert payload["candidate_count"] == 2
    assert payload["selected_action_count"] == 1
    assert payload["skipped_action_count"] == 1
    assert payload["total_positive_delta"] == 0.05


def test_memory_confidence_policy_respects_operation_limit(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    first = MemoryRecord(title="first", body="body", confidence=0.5)
    second = MemoryRecord(title="second", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([first, second])

    payload = run_memory_confidence_policy_profile(
        profile,
        dry_run=True,
        limit=2,
        max_total_operations=1,
    )

    assert payload["candidate_count"] == 2
    assert payload["selected_action_count"] == 1
    assert payload["skipped_action_count"] == 1
