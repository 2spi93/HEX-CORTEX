import json

from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_readiness_refresh_cli import main
from hex_cortex.memory.schemas import MemoryRecord


def test_profile_readiness_refresh_cli_outputs_gate_decision(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.5)]
    )

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["refresh_type"] == "profile_readiness_gate_snapshot_refresh"
    assert payload["decision"] == "block"
    assert payload["snapshot_count"] == 1
