import json

from hex_cortex.memory.profile_skill_cli import main


def test_profile_skill_cli_outputs_score_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["score_type"] == "world_state_skill_score"
    assert payload["score_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "world_state_skill_score"
    assert summary["total_score_count"] == 1
