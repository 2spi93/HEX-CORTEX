import json

from hex_cortex.memory.profile_latent_cli import main


def test_profile_state_cli_outputs_payload_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["latent_type"] == "latent_state_compression"
    assert payload["latent_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "latent_state"
    assert summary["total_latent_count"] == 1
