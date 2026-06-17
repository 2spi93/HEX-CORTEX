import json

from hex_cortex.memory.profile_learning_cli import main


def test_profile_learning_cli_outputs_learning_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["replay_type"] == "planner_replay_learning"
    assert payload["replay_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "planner_replay_learning"
    assert summary["total_replay_count"] == 1
