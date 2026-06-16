import json

from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
)
from hex_cortex.memory.confidence_recovery import RECOVERY_REASON
from hex_cortex.memory.confidence_recovery_cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


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


def test_memory_confidence_recovery_cli_defaults_to_dry_run(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.59, access_count=2)
    LocalMemoryJsonlStore(memory_path).save([memory])
    MemoryConfidenceAuditJsonlStore(audit_path).save([decay_audit(memory.memory_id)])

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["candidate_count"] == 1
    assert payload["recovered_count"] == 1
    assert persisted.confidence == 0.59


def test_memory_confidence_recovery_cli_apply_writes_audit(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.59, access_count=2)
    LocalMemoryJsonlStore(memory_path).save([memory])
    MemoryConfidenceAuditJsonlStore(audit_path).save([decay_audit(memory.memory_id)])

    exit_code = main([
        str(profile),
        "--recovery-amount",
        "0.02",
        "--apply",
    ])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert exit_code == 0
    assert payload["applied"] is True
    assert payload["audit_records_written"] == 1
    assert persisted.confidence == 0.6
    assert audits[-1].reason == RECOVERY_REASON
    assert audits[-1].delta == 0.01
