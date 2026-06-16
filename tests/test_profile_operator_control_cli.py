import json

from hex_cortex.memory.profile_operator_control_cli import main


def test_profile_operator_control_cli_outputs_compact_payload(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["control_type"] == "profile_operator_control"
    assert payload["decision"] == "block"
    assert payload["status"] == "blocked"
