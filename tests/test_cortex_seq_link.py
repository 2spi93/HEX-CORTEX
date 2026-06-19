from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_seq_link import build_cortex_seq_link
from hex_cortex.memory.cortex_surprise_registry import (
    build_cortex_surprise_registry,
)
from hex_cortex.memory.cortex_transition_registry import (
    build_cortex_transition_registry,
)


def test_seq_link_exposes_seq_build() -> None:
    registry = build_cortex_seq_link()

    assert sorted(registry) == ["seq.build"]
    unit = registry["seq.build"]
    assert unit.mutates_receipt is True
    assert unit.requires_operator is False


def test_seq_link_runs_through_bus(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    registry = combine_cortex_registries(
        build_cortex_transition_registry(),
        build_cortex_surprise_registry(),
        build_cortex_seq_link(),
    )
    plan = [
        {
            "name": "seq.build",
            "kwargs": {
                "profile": profile,
                "initial_state": {
                    "state_allowed": True,
                    "state_hash": "state-a",
                },
                "transition_record": {
                    "transition_allowed": True,
                    "source_state_hash": "state-a",
                    "transition_hash": "transition-a",
                    "action_id": "inspect",
                },
                "observed_state": {
                    "state_allowed": True,
                    "state_hash": "state-b",
                },
                "error_record": {
                    "prediction_error_allowed": True,
                    "transition_hash": "transition-a",
                    "observed_state_hash": "state-b",
                    "prediction_error_hash": "error-a",
                    "surprise_score": 0.3,
                    "surprise_level": "medium",
                    "learning_signal": "bounded_update",
                    "next_action": "review_prediction",
                },
            },
        }
    ]

    payload = run_cortex_units(registry, plan)

    assert payload["bus_allowed"] is True
    output = payload["results"][0]["output"]
    record = output["seq_records"][0]
    assert record["seq_allowed"] is True
    assert record["seq_index"] == 0
    assert record["learning_signal"] == "bounded_update"
