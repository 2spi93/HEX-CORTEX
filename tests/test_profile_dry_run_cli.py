import json

from hex_cortex.memory.profile_dry_run_cli import main


def test_profile_dry_run_cli_outputs_dry_run_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dry_run_type"] == "registry_review_dry_run"
    assert payload["dry_run_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "registry_review_dry_run"
    assert summary["total_dry_run_count"] == 1
