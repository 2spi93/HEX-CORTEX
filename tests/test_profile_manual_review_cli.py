import json

from hex_cortex.memory.profile_manual_review_cli import main


def test_profile_manual_review_cli_outputs_note_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--choice", "hold", "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["note_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["total_note_count"] == 1
    assert summary["latest_operator_choice"] == "hold"
