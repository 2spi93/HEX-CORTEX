import json

from hex_cortex.memory.profile_artifact_cli import main


def test_profile_artifact_cli_outputs_artifact_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["artifact_type"] == "review_activation_artifact"
    assert payload["artifact_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "review_activation_artifact"
    assert summary["total_artifact_count"] == 1
