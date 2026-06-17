import json

from hex_cortex.memory.profile_score_cli import main


def test_profile_score_cli_outputs_missing_trace_score(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["evaluation_type"] == "cognitive_trace_evaluation"
    assert payload["evaluation_record"]["verdict"] == "trace_missing"

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "cognitive_trace_evaluation"
    assert summary["total_evaluation_count"] == 1
