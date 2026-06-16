from pathlib import Path


def test_profile_next_action_contract_documents_hexnext() -> None:
    content = Path("docs/profile_next_action_contract.md").read_text(
        encoding="utf-8"
    )

    assert "hexnext" in content
    assert "run_cortex_pipeline" in content
    assert "repair_profile_readiness" in content
