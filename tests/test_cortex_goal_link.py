from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_goal_link import build_cortex_goal_link
from hex_cortex.memory.cortex_transition_registry import (
    build_cortex_transition_registry,
)


def test_goal_link_exposes_goal_and_cost_units() -> None:
    registry = build_cortex_goal_link()

    assert sorted(registry) == ["cost.evaluate", "goal.build"]
    assert registry["goal.build"].mutates_receipt is True
    assert registry["cost.evaluate"].requires_operator is False


def test_goal_and_cost_run_through_bus(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    registry = combine_cortex_registries(
        build_cortex_transition_registry(),
        build_cortex_goal_link(),
    )

    goal_payload = run_cortex_units(
        registry,
        [
            {
                "name": "goal.build",
                "kwargs": {
                    "profile": profile,
                    "goal_id": "understand_dashboard",
                    "desired_capabilities": [
                        "screen_vision",
                        "voice_input",
                    ],
                    "target_confidence": 0.8,
                    "max_horizon_steps": 8,
                    "max_total_cost": 0.5,
                    "priority": 0.9,
                },
            }
        ],
    )
    goal = goal_payload["results"][0]["output"]["goal_records"][0]

    cost_payload = run_cortex_units(
        registry,
        [
            {
                "name": "cost.evaluate",
                "kwargs": {
                    "profile": profile,
                    "goal_record": goal,
                    "candidate_state": {
                        "transition_allowed": True,
                        "transition_hash": "transition-hash",
                        "predicted_state_hash": "predicted-state-hash",
                        "predicted_capabilities": [
                            "screen_vision",
                            "voice_input",
                        ],
                        "predicted_average_confidence": 0.9,
                    },
                    "risk_penalty": 0.1,
                    "surprise_score": 0.1,
                    "horizon_steps": 1,
                },
            }
        ],
    )

    assert goal_payload["bus_allowed"] is True
    assert cost_payload["bus_allowed"] is True
    record = cost_payload["results"][0]["output"]["cost_records"][0]
    assert record["goal_satisfied"] is True
    assert record["within_cost_budget"] is True
    assert record["decision"] == "accept_candidate"
