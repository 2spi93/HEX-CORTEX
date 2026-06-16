from pathlib import Path


def test_profile_operator_contract_documents_canonical_alias() -> None:
    content = Path("docs/profile_operator_control_contract.md").read_text(
        encoding="utf-8"
    )

    assert "profile_control_cli" in content
    assert "strict exit code" in content
    assert "profile-operator-status.jsonl" in content
