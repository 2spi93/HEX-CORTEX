from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_surprise_registry import (
    build_cortex_surprise_registry,
)
from hex_cortex.memory.cortex_transition_registry import (
    build_cortex_transition_registry,
)


def test_surprise_registry_exposes_surprise_build() -> None:
    registry = build_cortex_surprise_registry()

    assert sorted(registry) == ["surprise.build"]
    unit = registry["surprise.build"]
    assert unit.mutates_receipt is True
    assert unit.requires_operator is False


def test_surprise_registry_runs_through_bus(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    registry = combine_cortex_registries(
        build_cortex_transition_registry(),
        build_cortex_surprise_registry(),
    )
    plan = [
        {
            "name": "surprise.build",
            "kwargs": {
                "profile": profile,
                "transition_record": {
                    "transition_allowed": True,
                    "transition_hash": "transition-hash",
                    "predicted_state_hash": "predicted-state-hash",
                    "predicted_capabilities": ["screen_vision"],
                    "predicted_average_confidence": 0.8,
                },
                "observed_state": {
                    "state_allowed": True,
                    "state_hash": "observed-state-hash",
                    "capabilities": ["screen_vision"],
                    "average_confidence": 0.8,
                },
            },
        }
    ]

    payload = run_cortex_units(registry, plan)

    assert payload["bus_allowed"] is True
    output = payload["results"][0]["output"]
    record = output["prediction_error_records"][0]
    assert record["prediction_error_allowed"] is True
    assert record["surprise_score"] == 0.0
    assert record["surprise_level"] == "low"
