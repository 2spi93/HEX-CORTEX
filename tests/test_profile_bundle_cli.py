import json

from hex_cortex.memory.profile_bundle_cli import main


def test_profile_bundle_cli_outputs_bundle_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["bundle_type"] == "review_audit_bundle"
    assert payload["bundle_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "review_audit_bundle"
    assert summary["total_bundle_count"] == 1
