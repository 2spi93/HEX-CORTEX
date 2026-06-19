from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_transition_registry import (
    build_cortex_transition_registry,
)
from hex_cortex.memory.cortex_world_flow import build_cortex_world_flow_registry


def test_transition_registry_exposes_transition_build() -> None:
    registry = build_cortex_transition_registry()

    assert sorted(registry) == ["transition.build"]
    unit = registry["transition.build"]
    assert unit.mutates_receipt is True
    assert unit.requires_operator is False


def test_transition_registry_runs_through_bus(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    registry = combine_cortex_registries(
        build_cortex_world_flow_registry(),
        build_cortex_transition_registry(),
    )
    current_state = {
        "state_allowed": True,
        "state_hash": "state-hash",
        "capabilities": ["screen_vision"],
        "average_confidence": 0.8,
    }
    plan = [
        {
            "name": "transition.build",
            "kwargs": {
                "profile": profile,
                "current_state": current_state,
                "action_context": {
                    "action_id": "inspect_dashboard",
                    "expected_capabilities": ["voice_input"],
                },
                "horizon_steps": 1,
            },
        }
    ]

    payload = run_cortex_units(registry, plan)

    assert payload["bus_allowed"] is True
    output = payload["results"][0]["output"]
    record = output["transition_records"][0]
    assert record["transition_allowed"] is True
    assert record["predicted_capabilities"] == [
        "screen_vision",
        "voice_input",
    ]
