import json

from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore
from hex_cortex.memory.confidence_policy_cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_memory_confidence_policy_cli_defaults_to_dry_run(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["selected_action_count"] == 1
    assert payload["actions"][0]["action_type"] == "confirmation"
    assert persisted.confidence == 0.5


def test_memory_confidence_policy_cli_apply_writes_audit(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="m", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main([
        str(profile),
        "--max-total-positive-delta",
        "0.05",
        "--apply",
    ])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert exit_code == 0
    assert payload["applied"] is True
    assert payload["audit_records_written"] == 1
    assert persisted.confidence == 0.55
    assert audits[-1].reason == "policy_retrieval_confirmed"
