from hex_cortex.memory.cortex_action_link import build_cortex_action_link
from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_goal_link import build_cortex_goal_link


def test_action_link_exposes_action_propose() -> None:
    registry = build_cortex_action_link()

    assert sorted(registry) == ["action.propose"]
    unit = registry["action.propose"]
    assert unit.mutates_receipt is True
    assert unit.requires_operator is False


def test_action_proposal_runs_through_bus(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    registry = combine_cortex_registries(
        build_cortex_goal_link(),
        build_cortex_action_link(),
    )
    plan = [
        {
            "name": "action.propose",
            "kwargs": {
                "profile": profile,
                "goal_record": {
                    "goal_allowed": True,
                    "goal_id": "understand_dashboard",
                    "goal_hash": "goal-hash",
                    "desired_capabilities": [
                        "screen_vision",
                        "voice_input",
                    ],
                    "target_confidence": 0.8,
                    "max_horizon_steps": 8,
                    "max_total_cost": 0.5,
                },
                "current_state": {
                    "state_allowed": True,
                    "state_hash": "state-hash",
                    "capabilities": ["screen_vision"],
                    "average_confidence": 0.6,
                },
                "candidate_actions": [
                    {
                        "action_id": "analyze_locally",
                        "output_id": "generate_plan",
                        "expected_capabilities": ["voice_input"],
                        "confidence_delta": 0.2,
                        "risk_penalty": 0.05,
                        "surprise_score": 0.05,
                        "horizon_steps": 1,
                    }
                ],
            },
        }
    ]

    payload = run_cortex_units(registry, plan)

    assert payload["bus_allowed"] is True
    record = payload["results"][0]["output"]["proposal_records"][0]
    assert record["proposal_allowed"] is True
    assert record["recommended_action_id"] == "analyze_locally"
    assert record["action_executed"] is False
