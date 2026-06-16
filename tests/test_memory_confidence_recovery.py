from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
)
from hex_cortex.memory.confidence_recovery import (
    RECOVERY_REASON,
    MemoryConfidenceRecoveryPlanner,
    run_memory_confidence_recovery_profile,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def decay_audit(memory_id: str, delta: float = -0.01) -> MemoryConfidenceAuditRecord:
    return MemoryConfidenceAuditRecord(
        memory_id=memory_id,
        reason="stale_memory_confidence_decay",
        before_confidence=0.6,
        after_confidence=0.59,
        delta=delta,
        changed=True,
        before_access_count=2,
        after_access_count=2,
    )


def test_memory_confidence_recovery_plan_uses_unrecovered_decay() -> None:
    memory = MemoryRecord(title="m", body="body", confidence=0.59, access_count=2)
    plan = MemoryConfidenceRecoveryPlanner(recovery_amount=0.02).plan(
        [memory],
        [decay_audit(memory.memory_id, delta=-0.03)],
        limit=5,
    )

    assert plan.total_memory_count == 1
    assert plan.decayed_memory_count == 1
    assert plan.candidate_count == 1
    assert plan.candidates[0].memory_id == memory.memory_id
    assert plan.candidates[0].unrecovered_decay == 0.03
    assert plan.candidates[0].after_confidence == 0.61
    assert plan.candidates[0].reason == RECOVERY_REASON


def test_memory_confidence_recovery_respects_previous_recovery() -> None:
    memory = MemoryRecord(title="m", body="body", confidence=0.61, access_count=3)
    audits = [
        decay_audit(memory.memory_id, delta=-0.03),
        MemoryConfidenceAuditRecord(
            memory_id=memory.memory_id,
            reason=RECOVERY_REASON,
            before_confidence=0.59,
            after_confidence=0.61,
            delta=0.02,
            changed=True,
            before_access_count=2,
            after_access_count=3,
        ),
    ]

    plan = MemoryConfidenceRecoveryPlanner(recovery_amount=0.02).plan(
        [memory],
        audits,
        limit=5,
    )

    assert plan.candidate_count == 1
    assert plan.candidates[0].unrecovered_decay == 0.01
    assert plan.candidates[0].recovery_amount == 0.01


def test_memory_confidence_recovery_dry_run_does_not_mutate_or_audit(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.59, access_count=2)
    LocalMemoryJsonlStore(memory_path).save([memory])
    MemoryConfidenceAuditJsonlStore(audit_path).save([decay_audit(memory.memory_id)])

    payload = run_memory_confidence_recovery_profile(profile, dry_run=True)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert payload["candidate_count"] == 1
    assert payload["recovered_count"] == 1
    assert payload["audit_records_written"] == 0
    assert persisted.confidence == 0.59
    assert len(audits) == 1


def test_memory_confidence_recovery_apply_mutates_and_audits(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.59, access_count=2)
    LocalMemoryJsonlStore(memory_path).save([memory])
    MemoryConfidenceAuditJsonlStore(audit_path).save([decay_audit(memory.memory_id)])

    payload = run_memory_confidence_recovery_profile(
        profile,
        dry_run=False,
        recovery_amount=0.02,
    )
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert payload["applied"] is True
    assert payload["audit_records_written"] == 1
    assert persisted.confidence == 0.6
    assert persisted.access_count == 3
    assert audits[-1].reason == RECOVERY_REASON
    assert audits[-1].delta == 0.01


def test_memory_confidence_recovery_ignores_memory_without_decay() -> None:
    memory = MemoryRecord(title="m", body="body", confidence=0.59, access_count=2)

    plan = MemoryConfidenceRecoveryPlanner().plan([memory], [], limit=5)

    assert plan.candidate_count == 0
