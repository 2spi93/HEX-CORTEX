import json

from hex_cortex.memory.confidence_policy_telemetry_cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_policy_telemetry_cli_records_report(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main([
        str(profile),
        "--limit",
        "1",
        "--max-total-positive-delta",
        "0.05",
        "--pretty",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["record_type"] == "memory_confidence_policy_telemetry"
    assert payload["telemetry_record_count"] == 1
    assert payload["telemetry_record"]["selected_action_count"] == 1
    assert payload["telemetry_record"]["policy_report"]["dry_run"] is True


def test_policy_telemetry_cli_outputs_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.8, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([memory])
    main([str(profile)])
    capsys.readouterr()

    exit_code = main([str(profile), "--summary", "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["inspect_type"] == "memory_confidence_policy_telemetry"
    assert payload["total_record_count"] == 1
    assert payload["stable_zero_action_count"] == 1
