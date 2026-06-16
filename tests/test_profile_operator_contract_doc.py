from pathlib import Path


def test_profile_operator_contract_documents_hexctl() -> None:
    content = Path("docs/profile_operator_control_contract.md").read_text(
        encoding="utf-8"
    )

    assert "hexctl" in content
    assert "profile-operator-status.jsonl" in content
