import json

from hex_cortex.cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_cli_inspect_profile_includes_memory_pruning_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    first = MemoryRecord(title="first", body="body", confidence=0.1)
    second = MemoryRecord(title="second", body="body", confidence=0.9)
    LocalMemoryJsonlStore(memory_path).save([first, second])

    main(["--inspect-profile", str(profile)])
    payload = json.loads(capsys.readouterr().out)
    pruning = payload["memory_pruning"]
    persisted = LocalMemoryJsonlStore(memory_path).load()

    assert pruning["dry_run"] is True
    assert pruning["archive_count"] == 1
    assert pruning["keep_count"] == 1
    assert pruning["changed_count"] == 1
    assert [memory.visible for memory in persisted] == [True, True]
