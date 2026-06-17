import json

from hex_cortex.memory.profile_review_outcome_cli import main


def test_profile_review_outcome_cli_outputs_outcome_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["outcome_type"] == "operator_review_outcome"
    assert payload["outcome_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "operator_review_outcome"
    assert summary["total_outcome_count"] == 1
