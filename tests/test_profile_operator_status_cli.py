import json

from hex_cortex.memory.profile_operator_status_cli import main

EXPECTED_KEYS = {"status", "decision", "reason", "score", "latest_snapshot_id"}


def test_profile_operator_status_cli_outputs_minimal_payload(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert set(payload) == EXPECTED_KEYS
    assert payload["status"] == "blocked"
    assert payload["decision"] == "block"
