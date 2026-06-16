import json

from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_inspect_cli import inspect_profile_plus, main
from hex_cortex.memory.schemas import MemoryRecord


def test_profile_inspect_plus_includes_memory_confidence_plan(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])

    payload = inspect_profile_plus(profile, limit=2)
    plan = payload["memory_confidence_plan"]

    assert payload["inspect_type"] == "profile"
    assert plan["candidate_count"] == 1
    assert plan["limit"] == 2
    assert plan["candidates"][0]["memory_id"] == memory.memory_id


def test_profile_inspect_plus_entrypoint_outputs_json(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])

    exit_code = main([str(profile), "--limit", "1", "--pretty"])
    payload = json.loads(capsys.readouterr().out)
    plan = payload["memory_confidence_plan"]

    assert exit_code == 0
    assert plan["candidate_count"] == 1
    assert plan["limit"] == 1
