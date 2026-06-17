import json

from hex_cortex.memory.profile_world_cli import main


def test_profile_world_cli_outputs_candidate_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["candidate_type"] == "world_state_candidate"
    assert payload["candidate_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "world_state_candidate"
    assert summary["total_candidate_count"] == 1
