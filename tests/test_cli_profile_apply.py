import json

from hex_cortex.cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_cli_profile_memory_apply_updates_file_and_backup(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    backup_path = profile / "memory.prune-backup.jsonl"
    first = MemoryRecord(title="first", body="body", confidence=0.1)
    second = MemoryRecord(title="second", body="body", confidence=0.9)
    LocalMemoryJsonlStore(memory_path).save([first, second])
    flag = "--apply-" + "memory-pruning-profile"

    exit_code = main([flag, str(profile)])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()
    backup = LocalMemoryJsonlStore(backup_path).load()

    assert exit_code == 0
    assert payload["applied"] is True
    assert payload["backup_written"] is True
    assert payload["changed_count"] == 1
    assert payload["visible_after"] == 1
    assert not persisted[0].visible
    assert persisted[1].visible
    assert backup[0].visible
    assert backup[1].visible
