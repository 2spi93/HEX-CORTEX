from hex_cortex.memory.cortex_links import get_cortex_link
from hex_cortex.memory.cortex_links import list_cortex_links


def test_cortex_links_include_candidate_bridges() -> None:
    rows = list_cortex_links()
    ids = {row["link_id"] for row in rows}

    assert "formal_math_link" in ids
    assert "repo_coding_link_a" in ids
    assert "repo_coding_link_b" in ids
    assert "tool_protocol_link" in ids


def test_get_cortex_link() -> None:
    payload = get_cortex_link("formal_math_link")

    assert payload["state"] == "candidate"
    assert payload["default_mode"] == "manual_until_receipts"


def test_unknown_cortex_link_blocks() -> None:
    payload = get_cortex_link("unknown")

    assert payload["state"] == "blocked"
    assert payload["blocker"] == "unknown_link_candidate"
