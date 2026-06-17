import json

from hex_cortex.memory.profile_registry_review_cli import main


def test_profile_registry_review_cli_outputs_document_and_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["document_type"] == "skill_registry_review_document"
    assert payload["document_count"] == 1

    exit_code = main([str(profile), "--summary", "--pretty"])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["inspect_type"] == "skill_registry_review_document"
    assert summary["total_document_count"] == 1
