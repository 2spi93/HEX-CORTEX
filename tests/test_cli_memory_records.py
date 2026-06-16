import json

from hex_cortex.cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord, MemoryType


def test_cli_inspect_memory_records_reports_ids_and_confidence(tmp_path, capsys) -> None:
    memory_path = tmp_path / "memory.jsonl"
    memory = MemoryRecord(
        title="Preference",
        body="Operator prefers local-first workflows.",
        memory_type=MemoryType.OPERATOR_PREFERENCE,
        confidence=0.7,
        access_count=2,
        tags=["operator", "preference"],
    )
    LocalMemoryJsonlStore(memory_path).save([memory])

    exit_code = main(["--inspect-memory-records", str(memory_path), "--pretty"])
    payload = json.loads(capsys.readouterr().out)
    record = payload["records"][0]

    assert exit_code == 0
    assert payload["inspect_type"] == "memory_records"
    assert payload["total_memory_count"] == 1
    assert record["memory_id"] == memory.memory_id
    assert record["title"] == "Preference"
    assert record["memory_type"] == "operator_preference"
    assert record["confidence"] == 0.7
    assert record["access_count"] == 2
    assert record["tags"] == ["operator", "preference"]
