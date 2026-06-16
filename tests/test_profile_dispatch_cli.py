import json

from hex_cortex.memory.profile_next_action_dispatch_cli import main


def test_profile_dispatch_cli_outputs_dispatch_status(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dispatch_type"] == "profile_next_action_dispatch"
    assert payload["dispatch_status"] == "skipped"
