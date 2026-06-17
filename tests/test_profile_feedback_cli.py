import json

from hex_cortex.memory.profile_feedback_cli import main


def test_profile_feedback_cli_outputs_feedback_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["feedback_type"] == "skill_outcome_feedback"
    assert payload["feedback_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "skill_outcome_feedback"
    assert summary["total_feedback_count"] == 1
