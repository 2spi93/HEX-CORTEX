import json

from hex_cortex.cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord, MemoryType


def test_cli_inspect_memory_reports_memory_type_counts(tmp_path, capsys) -> None:
    memory_path = tmp_path / "memory.jsonl"
    LocalMemoryJsonlStore(memory_path).save(
        [
            MemoryRecord(title="one", body="body"),
            MemoryRecord(
                title="two",
                body="body",
                memory_type=MemoryType.OPERATOR_PREFERENCE,
            ),
        ]
    )

    main(["--inspect-memory", str(memory_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["memory_type_counts"] == {
        "episode": 1,
        "operator_preference": 1,
    }
