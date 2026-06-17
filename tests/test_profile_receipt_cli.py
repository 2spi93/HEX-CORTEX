import json

from hex_cortex.memory.profile_receipt_cli import main


def test_profile_receipt_cli_outputs_receipt_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["receipt_type"] == "controlled_execution_receipt"
    assert payload["receipt_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "controlled_execution_receipt"
    assert summary["total_receipt_count"] == 1
