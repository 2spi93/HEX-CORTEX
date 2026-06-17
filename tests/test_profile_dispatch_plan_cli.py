import json

from hex_cortex.memory.profile_dispatch_plan_cli import main


def test_profile_dispatch_plan_cli_outputs_payload(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["profile_path"] == str(tmp_path / "profile")
