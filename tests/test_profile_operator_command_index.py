from pathlib import Path


def test_profile_operator_command_index_keeps_single_canonical_alias() -> None:
    content = Path("docs/profile_operator_command_index.md").read_text(
        encoding="utf-8"
    )

    assert "Canonical human command" in content
    assert "profile_control_cli" in content
    assert "Diagnostic-only modules" in content
