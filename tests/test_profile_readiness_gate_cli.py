import json

from hex_cortex.memory.profile_readiness_gate_cli import main


def test_profile_readiness_gate_cli_blocks_missing_snapshot(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["gate_type"] == "profile_readiness_gate"
    assert payload["decision"] == "block"
    assert payload["reason"] == "readiness_snapshot_missing"
