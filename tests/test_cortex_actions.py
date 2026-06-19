from hex_cortex.memory.cortex_outputs import get_cortex_output
from hex_cortex.memory.cortex_outputs import list_cortex_outputs


def test_output_catalog_has_expected_entries() -> None:
    rows = list_cortex_outputs()
    ids = {row["output_id"] for row in rows}

    assert "write_text" in ids
    assert "write_code" in ids
    assert "write_document" in ids
    assert "write_structured_data" in ids
    assert "generate_plan" in ids
    assert "annotate_visual" in ids


def test_get_known_output() -> None:
    payload = get_cortex_output("write_code")

    assert payload["state"] == "candidate"
    assert payload["requires_operator"] is False
    assert payload["raw_input_persistence_allowed"] is False


def test_unknown_output_is_blocked() -> None:
    payload = get_cortex_output("unknown")

    assert payload["state"] == "blocked"
    assert payload["blocker"] == "unknown_output_capability"
