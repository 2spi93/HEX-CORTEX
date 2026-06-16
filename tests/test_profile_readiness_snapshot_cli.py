import json

from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_readiness_snapshot_cli import main
from hex_cortex.memory.schemas import MemoryRecord


def test_profile_readiness_snapshot_cli_records_and_summarizes(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.5)]
    )

    exit_code = main([str(profile), "--pretty"])
    record_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert record_payload["record_type"] == "profile_readiness_snapshot"
    assert record_payload["snapshot_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["inspect_type"] == "profile_readiness_snapshot"
    assert summary["total_snapshot_count"] == 1
    assert summary["latest_verdict"] == "profile_blocked"
