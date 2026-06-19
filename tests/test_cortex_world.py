from hex_cortex.memory.cortex_world import compute_cortex_world_readiness


def test_world_readiness_ready_candidate() -> None:
    payload = compute_cortex_world_readiness(
        multimodal_inputs=1.0,
        persistent_memory=1.0,
        predictive_state=1.0,
        planning_loop=1.0,
        surprise_detection=1.0,
        safety_receipts=1.0,
    )

    assert payload["world_allowed"] is True
    assert payload["world_status"] == "ready_candidate"
    assert payload["score"] == 100.0
    assert payload["missing_layers"] == []


def test_world_readiness_not_ready_lists_missing_layers() -> None:
    payload = compute_cortex_world_readiness(
        multimodal_inputs=0.2,
        persistent_memory=0.7,
        predictive_state=0.1,
        planning_loop=0.6,
        surprise_detection=0.1,
        safety_receipts=1.0,
    )

    assert payload["world_allowed"] is True
    assert payload["world_status"] == "not_ready"
    assert "multimodal_inputs" in payload["missing_layers"]
    assert "predictive_state" in payload["missing_layers"]
    assert payload["next_action"] == "fill_world_model_layers"


def test_world_readiness_blocks_out_of_range() -> None:
    payload = compute_cortex_world_readiness(
        multimodal_inputs=1.2,
        persistent_memory=1.0,
        predictive_state=1.0,
        planning_loop=1.0,
        surprise_detection=1.0,
        safety_receipts=1.0,
    )

    assert payload["world_allowed"] is False
    assert "multimodal_inputs_out_of_range" in payload["blockers"]
