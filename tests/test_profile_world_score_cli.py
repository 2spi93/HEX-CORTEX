import json

from hex_cortex.memory.profile_world_score_cli import main


def test_profile_world_score_cli_outputs_missing_candidate_score(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["evaluation_type"] == "world_state_candidate_evaluation"
    assert payload["evaluation_record"]["verdict"] == "world_candidate_missing"

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "world_state_candidate_evaluation"
    assert summary["total_evaluation_count"] == 1
