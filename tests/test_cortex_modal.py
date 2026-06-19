from hex_cortex.memory.cortex_modal import describe_cortex_multimodal_capability
from hex_cortex.memory.cortex_modal import list_cortex_multimodal_capabilities


def test_multimodal_capabilities_include_screen_camera_voice() -> None:
    rows = list_cortex_multimodal_capabilities()
    ids = {row["capability_id"] for row in rows}

    assert "screen_vision" in ids
    assert "camera_vision" in ids
    assert "voice_input" in ids
    assert "voice_output" in ids


def test_screen_vision_is_operator_approved_readonly() -> None:
    payload = describe_cortex_multimodal_capability("screen_vision")

    assert payload["default_mode"] == "operator_approved_readonly"
    assert payload["raw_input_persistence_allowed"] is False


def test_unknown_multimodal_capability_blocks() -> None:
    payload = describe_cortex_multimodal_capability("unknown")

    assert payload["status"] == "blocked"
    assert payload["blocker"] == "unknown_multimodal_capability"
