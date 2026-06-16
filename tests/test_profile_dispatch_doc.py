from pathlib import Path


def test_profile_dispatch_doc_mentions_hexdispatch() -> None:
    content = Path("docs/profile_next_action_dispatch_contract.md").read_text(
        encoding="utf-8"
    )

    assert "hexdispatch" in content
