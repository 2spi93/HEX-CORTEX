import json

from hex_cortex.memory.profile_action_cost_cli import main


def test_profile_cost_cli_outputs_payload_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["cost_type"] == "action_cost_model"
    assert payload["cost_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "action_cost_model"
    assert summary["total_cost_count"] == 1
