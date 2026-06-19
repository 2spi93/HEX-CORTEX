from hex_cortex.memory.cortex_modal import describe_cortex_multimodal_capability
from hex_cortex.memory.cortex_modal import list_cortex_multimodal_capabilities


def test_multimodal_catalog_includes_3d_vision() -> None:
    rows = list_cortex_multimodal_capabilities()
    ids = {row["capability_id"] for row in rows}

    assert "vision_3d" in ids


def test_3d_vision_contract_is_readonly() -> None:
    payload = describe_cortex_multimodal_capability("vision_3d")

    assert payload["input_type"] == "multi_view_depth_point_cloud_or_mesh"
    assert payload["default_mode"] == "operator_approved_readonly"
    assert payload["raw_input_persistence_allowed"] is False
