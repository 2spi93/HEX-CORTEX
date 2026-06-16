import json

from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_operational_readiness_cli import main
from hex_cortex.memory.schemas import MemoryRecord


def test_profile_operational_readiness_cli_outputs_json(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.5)]
    )

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["readiness_type"] == "profile_operational_readiness"
    assert payload["verdict"] == "profile_blocked"
