import json

from hex_cortex.memory.profile_full_status_cli import main


def test_profile_status_all_cli_outputs_sections(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["profile_path"] == str(profile)
    assert "pack" in payload
    assert "status" in payload
    assert "freeze" in payload
    assert "invariants" in payload
