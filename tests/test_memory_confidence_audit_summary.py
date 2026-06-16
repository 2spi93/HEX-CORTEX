from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
)
from hex_cortex.memory.confidence_audit_summary import summarize_memory_confidence_audit


def test_memory_confidence_audit_summary_counts_positive_and_negative_deltas(tmp_path) -> None:
    audit_path = tmp_path / "memory-confidence-audit.jsonl"
    MemoryConfidenceAuditJsonlStore(audit_path).save([
        MemoryConfidenceAuditRecord(
            memory_id="mem_a",
            reason="retrieval_confirmed",
            before_confidence=0.5,
            after_confidence=0.55,
            delta=0.05,
            changed=True,
            before_access_count=0,
            after_access_count=1,
        ),
        MemoryConfidenceAuditRecord(
            memory_id="mem_b",
            reason="stale_memory_confidence_decay",
            before_confidence=0.6,
            after_confidence=0.59,
            delta=-0.01,
            changed=True,
            before_access_count=2,
            after_access_count=2,
        ),
    ])

    summary = summarize_memory_confidence_audit(audit_path)

    assert summary["total_audit_count"] == 2
    assert summary["positive_delta_count"] == 1
    assert summary["negative_delta_count"] == 1
    assert summary["zero_delta_count"] == 0
    assert summary["total_positive_delta"] == 0.05
    assert summary["total_negative_delta"] == -0.01
    assert summary["net_delta"] == 0.04
    assert summary["reason_counts"] == {
        "retrieval_confirmed": 1,
        "stale_memory_confidence_decay": 1,
    }
    assert summary["latest_memory_id"] == "mem_b"
    assert summary["latest_delta"] == -0.01


def test_memory_confidence_audit_summary_handles_missing_audit_file(tmp_path) -> None:
    audit_path = tmp_path / "missing.jsonl"

    summary = summarize_memory_confidence_audit(audit_path)

    assert summary["exists"] is False
    assert summary["total_audit_count"] == 0
    assert summary["net_delta"] == 0
    assert summary["reason_counts"] == {}
