import json

from hex_cortex.memory.profile_review_cli import main


def test_profile_review_cli_outputs_packet_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["review_type"] == "operator_review_packet"
    assert payload["review_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "operator_review_packet"
    assert summary["total_review_count"] == 1
