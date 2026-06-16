import json

from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
)
from hex_cortex.memory.confidence_audit_cli import main


def test_memory_confidence_audit_cli_outputs_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    audit_path = profile / "memory-confidence-audit.jsonl"
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

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["inspect_type"] == "memory_confidence_audit_summary"
    assert payload["total_audit_count"] == 2
    assert payload["net_delta"] == 0.04
    assert payload["latest_reason"] == "stale_memory_confidence_decay"
