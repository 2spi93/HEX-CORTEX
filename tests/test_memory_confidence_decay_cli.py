import json
from datetime import UTC, datetime, timedelta

from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore
from hex_cortex.memory.confidence_decay_cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def timestamp_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def test_memory_confidence_decay_cli_defaults_to_dry_run(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(
        title="stale",
        body="body",
        confidence=0.8,
        access_count=1,
        last_accessed_at=timestamp_days_ago(60),
    )
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["candidate_count"] == 1
    assert persisted.confidence == 0.8


def test_memory_confidence_decay_cli_apply_writes_audit(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(
        title="stale",
        body="body",
        confidence=0.8,
        access_count=1,
        last_accessed_at=timestamp_days_ago(60),
    )
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main([
        str(profile),
        "--stale-after-days",
        "30",
        "--decay-amount",
        "0.05",
        "--apply",
    ])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert exit_code == 0
    assert payload["applied"] is True
    assert payload["audit_records_written"] == 1
    assert persisted.confidence == 0.75
    assert audits[0].delta == -0.05
