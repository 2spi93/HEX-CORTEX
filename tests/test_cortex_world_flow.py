from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_seen import build_cortex_seen
from hex_cortex.memory.cortex_state import build_cortex_state
from hex_cortex.memory.cortex_world_flow import build_cortex_world_flow_registry


def test_world_flow_registry_exposes_expected_units() -> None:
    registry = build_cortex_world_flow_registry()

    assert sorted(registry) == ["outputs.list", "seen.build", "state.build"]
    assert registry["seen.build"].requires_operator is True
    assert registry["state.build"].requires_operator is False


def test_seen_to_state_flow(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    seen = build_cortex_seen(
        profile,
        provider_id="local_image_file",
        summary="A dashboard is visible.",
        confidence=0.9,
        approved=True,
    )["seen_records"]
    state = build_cortex_state(profile, seen_records=seen)

    record = state["state_records"][0]
    assert record["state_allowed"] is True
    assert record["capabilities"] == ["screen_vision"]
    assert record["source_count"] == 1
    assert record["raw_inputs_saved"] is False


def test_outputs_list_runs_through_bus() -> None:
    registry = build_cortex_world_flow_registry()

    payload = run_cortex_units(
        registry,
        [{"name": "outputs.list", "kwargs": {}}],
    )

    assert payload["bus_allowed"] is True
    rows = payload["results"][0]["output"]
    ids = {row["output_id"] for row in rows}
    assert "write_text" in ids
    assert "write_code" in ids
    assert "generate_plan" in ids
