import json

from hex_cortex.memory.profile_run_cli import main


def test_profile_run_cli_outputs_cycle_payload(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["cycle_type"] == "profile_operator_cycle"
    assert payload["cycle_status"] == "plan_required"
