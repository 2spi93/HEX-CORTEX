import json

import pytest

from hex_cortex.cli import main
from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_cli_confirm_memory_profile_updates_memory_and_audit(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main(
        [
            "--confirm-memory-profile",
            str(profile),
            "--confirm-memory-id",
            memory.memory_id,
            "--confirm-memory-reason",
            "retrieval_confirmed",
            "--pretty",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    updated_memory = LocalMemoryJsonlStore(memory_path).load()[0]
    audit_records = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert exit_code == 0
    assert payload["confirmed"] is True
    assert payload["before_confidence"] == 0.5
    assert payload["after_confidence"] == 0.55
    assert payload["after_access_count"] == 1
    assert updated_memory.confidence == 0.55
    assert updated_memory.access_count == 1
    assert len(audit_records) == 1
    assert audit_records[0].reason == "retrieval_confirmed"


def test_cli_confirm_memory_profile_missing_memory_does_not_write_audit(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main(
        [
            "--confirm-memory-profile",
            str(profile),
            "--confirm-memory-id",
            "missing",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    unchanged_memory = LocalMemoryJsonlStore(memory_path).load()[0]

    assert exit_code == 0
    assert payload["confirmed"] is False
    assert payload["audit_written"] is False
    assert unchanged_memory.confidence == 0.5
    assert not audit_path.exists()


def test_cli_confirm_memory_profile_requires_memory_id(tmp_path) -> None:
    profile = tmp_path / "profile"

    with pytest.raises(ValueError, match="--confirm-memory-id is required"):
        main(["--confirm-memory-profile", str(profile)])


def test_cli_inspect_profile_reports_memory_confidence_audit(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])
    main([
        "--confirm-memory-profile",
        str(profile),
        "--confirm-memory-id",
        memory.memory_id,
    ])
    capsys.readouterr()

    main(["--inspect-profile", str(profile)])
    payload = json.loads(capsys.readouterr().out)
    confidence_audit = payload["memory_confidence_audit"]

    assert confidence_audit["total_audit_count"] == 1
    assert confidence_audit["latest_memory_id"] == memory.memory_id
    assert confidence_audit["latest_delta"] == 0.05
    assert payload["memory"]["average_confidence"] == 0.55
    assert payload["memory"]["access_count_total"] == 1
