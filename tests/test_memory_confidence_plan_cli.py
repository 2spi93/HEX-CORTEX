import json

from hex_cortex.memory.confidence_plan_cli import main, plan_memory_confidence_profile
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_memory_confidence_plan_profile_returns_candidates(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])

    payload = plan_memory_confidence_profile(profile, limit=3)

    assert payload["plan_type"] == "memory_confidence_profile"
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["memory_id"] == memory.memory_id
    assert payload["candidates"][0]["reasons"] == [
        "confidence_below_floor",
        "never_confirmed",
    ]


def test_memory_confidence_plan_entrypoint_outputs_json(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])

    exit_code = main([str(profile), "--limit", "1", "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["candidate_count"] == 1
    assert payload["limit"] == 1
    assert payload["candidates"][0]["memory_id"] == memory.memory_id
