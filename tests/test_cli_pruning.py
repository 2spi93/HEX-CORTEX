import json

from hex_cortex.cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_cli_prune_memory_profile_dry_run_reports_archive_candidates(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    weak_memory = MemoryRecord(
        title="Weak memory",
        body="Low confidence memory.",
        confidence=0.1,
    )
    healthy_memory = MemoryRecord(
        title="Healthy memory",
        body="High confidence memory.",
        confidence=0.9,
    )
    LocalMemoryJsonlStore(memory_path).save([weak_memory, healthy_memory])

    exit_code = main(["--prune-memory-profile", str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)
    persisted = LocalMemoryJsonlStore(memory_path).load()

    assert exit_code == 0
    assert payload["prune_type"] == "memory_profile"
    assert payload["dry_run"] is True
    assert payload["total_memory_count"] == 2
    assert payload["archive_count"] == 1
    assert payload["keep_count"] == 1
    assert payload["changed_count"] == 1
    assert payload["visible_before"] == 2
    assert payload["visible_after"] == 2
    assert [memory.visible for memory in persisted] == [True, True]


def test_cli_prune_memory_profile_handles_empty_profile(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"

    exit_code = main(["--prune-memory-profile", str(profile)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["total_memory_count"] == 0
    assert payload["decision_count"] == 0
    assert payload["changed_count"] == 0
    assert payload["changes"] == []
