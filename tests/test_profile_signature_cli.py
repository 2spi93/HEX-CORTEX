import json

from hex_cortex.memory.profile_signature_cli import main


def test_profile_signature_cli_outputs_packet_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["signature_type"] == "registry_review_signature_packet"
    assert payload["signature_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "registry_review_signature_packet"
    assert summary["total_signature_count"] == 1
