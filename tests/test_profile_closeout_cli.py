import json

from hex_cortex.memory.profile_closeout_cli import main


def test_profile_closeout_cli_outputs_closeout_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["closeout_type"] == "review_closeout_report"
    assert payload["closeout_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "review_closeout_report"
    assert summary["total_closeout_count"] == 1
