import json

from hex_cortex.memory.profile_audit_report_cli import main


def test_profile_audit_report_cli_outputs_audit_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["audit_type"] == "skill_execution_audit"
    assert payload["audit_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "skill_execution_audit"
    assert summary["total_audit_count"] == 1
