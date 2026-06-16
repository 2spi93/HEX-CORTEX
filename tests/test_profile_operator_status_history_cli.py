import json

from hex_cortex.memory.profile_operator_status_history_cli import main


def test_profile_operator_status_history_cli_records_and_summarizes(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"

    exit_code = main([str(profile), "--pretty"])
    record_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert record_payload["record_type"] == "profile_operator_status_history"
    assert record_payload["history_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["inspect_type"] == "profile_operator_status_history"
    assert summary["total_status_count"] == 1
    assert summary["latest_status"] == "blocked"
