import json

from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_operator_status_refresh_cli import main
from hex_cortex.memory.schemas import MemoryRecord

EXPECTED_KEYS = {"status", "decision", "reason", "score", "latest_snapshot_id"}


def test_profile_operator_status_refresh_cli_outputs_minimal_payload(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.5)]
    )

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert set(payload) == EXPECTED_KEYS
    assert payload["status"] == "blocked"
    assert payload["decision"] == "block"
