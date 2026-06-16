import json

from hex_cortex.memory.profile_next_action_cli import main


def test_profile_next_action_cli_outputs_next_action(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["action_type"] == "profile_next_action"
    assert payload["next_action"] == "repair_profile_readiness"
