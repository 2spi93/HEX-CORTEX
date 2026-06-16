import json

from hex_cortex.memory.profile_dispatch_preflight_cli import main


def test_profile_dispatch_preflight_cli_reports_blocked_profile(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["inspect_type"] == "profile_dispatch_preflight"
    assert payload["allowed"] is False
