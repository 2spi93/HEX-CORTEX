import json

from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore
from hex_cortex.memory.confidence_batch_cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_memory_confidence_batch_cli_defaults_to_dry_run(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main([str(profile), "--limit", "1", "--pretty"])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["candidate_count"] == 1
    assert payload["saturation_threshold"] == 0.7
    assert payload["apply_blocked_reason"] is None
    assert persisted.confidence == 0.5


def test_memory_confidence_batch_cli_apply_writes_audit(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main([
        str(profile),
        "--limit",
        "1",
        "--reason",
        "retrieval_confirmed",
        "--apply",
    ])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert exit_code == 0
    assert payload["dry_run"] is False
    assert payload["applied"] is True
    assert payload["audit_records_written"] == 1
    assert persisted.confidence == 0.55
    assert audits[0].reason == "retrieval_confirmed"


def test_memory_confidence_batch_cli_blocks_apply_with_safety_limit(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    first = MemoryRecord(title="first", body="body", confidence=0.5)
    second = MemoryRecord(title="second", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([first, second])

    exit_code = main([
        str(profile),
        "--limit",
        "2",
        "--max-total-delta",
        "0.05",
        "--apply",
    ])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()

    assert exit_code == 0
    assert payload["applied"] is False
    assert payload["apply_blocked_reason"] == "max_total_delta_exceeded"
    assert [memory.confidence for memory in persisted] == [0.5, 0.5]


def test_memory_confidence_batch_cli_uses_saturation_threshold(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(
        title="memory",
        body="body",
        confidence=0.65,
        access_count=1,
    )
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main([
        str(profile),
        "--saturation-threshold",
        "0.6",
        "--apply",
    ])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]

    assert exit_code == 0
    assert payload["applied"] is False
    assert payload["apply_blocked_reason"] == "no_eligible_candidates"
    assert payload["saturation_threshold"] == 0.6
    assert payload["saturated_memory_count"] == 1
    assert persisted.confidence == 0.65
