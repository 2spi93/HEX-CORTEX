import json

from hex_cortex.memory.profile_steps_cli import main


def test_profile_steps_cli_builds_and_summarizes_trace(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["trace_type"] == "cognitive_trace_build"
    assert payload["trace_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "cognitive_trace"
    assert summary["total_trace_count"] == 1
