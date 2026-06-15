import json

from hex_cortex.cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.pruning_audit import PruningAuditJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_cli_pruning_preview_writes_audit_record(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "pruning-audit.jsonl"
    LocalMemoryJsonlStore(memory_path).save(
        [MemoryRecord(title="memory", body="body", confidence=0.9)]
    )

    main(["--prune-memory-profile", str(profile)])
    payload = json.loads(capsys.readouterr().out)
    records = PruningAuditJsonlStore(audit_path).load()

    assert payload["audit_record_count"] == 1
    assert payload["audit_path"] == str(audit_path)
    assert records[0].operation == "preview"
    assert records[0].dry_run is True


def test_cli_pruning_apply_adds_second_audit_record(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "pruning-audit.jsonl"
    LocalMemoryJsonlStore(memory_path).save(
        [MemoryRecord(title="memory", body="body", confidence=0.9)]
    )
    main(["--prune-memory-profile", str(profile)])
    capsys.readouterr()
    flag = "--apply-" + "memory-pruning-profile"

    main([flag, str(profile)])
    payload = json.loads(capsys.readouterr().out)
    records = PruningAuditJsonlStore(audit_path).load()

    assert payload["audit_record_count"] == 2
    assert [record.operation for record in records] == ["preview", "apply"]
    assert records[1].applied is True


def test_cli_inspect_profile_reports_pruning_audit_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    LocalMemoryJsonlStore(memory_path).save(
        [MemoryRecord(title="memory", body="body", confidence=0.9)]
    )
    main(["--prune-memory-profile", str(profile)])
    capsys.readouterr()

    main(["--inspect-profile", str(profile)])
    payload = json.loads(capsys.readouterr().out)
    audit = payload["pruning_audit"]

    assert audit["total_audit_count"] == 1
    assert audit["operation_counts"] == {"preview": 1}
    assert audit["latest_operation"] == "preview"
