import json

from hex_cortex.memory.profile_registry_cli import main


def test_profile_registry_cli_outputs_match_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["match_type"] == "skill_registry_integration"
    assert payload["match_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "skill_registry_match"
    assert summary["total_match_count"] == 1
