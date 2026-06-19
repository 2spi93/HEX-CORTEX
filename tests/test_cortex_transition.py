from hex_cortex.memory.cortex_transition import CORTEX_TRANSITION_FILENAME
from hex_cortex.memory.cortex_transition import build_cortex_transition
from hex_cortex.memory.cortex_transition import summarize_cortex_transitions


def test_cortex_transition_imports() -> None:
    assert CORTEX_TRANSITION_FILENAME == "cortex-transition.jsonl"


def test_cortex_transition_predicts_next_state(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_transition(
        profile,
        current_state=_state(),
        action_context={
            "action_id": "inspect_dashboard",
            "expected_capabilities": ["voice_input"],
            "confidence_delta": 0.05,
        },
        horizon_steps=1,
    )

    record = payload["transition_records"][0]
    assert record["transition_allowed"] is True
    assert record["transition_basis"] == "deterministic_contract_v1"
    assert record["action_id"] == "inspect_dashboard"
    assert record["predicted_capabilities"] == [
        "screen_vision",
        "voice_input",
    ]
    assert record["predicted_average_confidence"] == 0.85
    assert isinstance(record["predicted_state_hash"], str)
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["raw_state_persisted"] is False
    assert record["next_action"] == "compare_observed_state"

    summary = summarize_cortex_transitions(
        profile / CORTEX_TRANSITION_FILENAME
    )
    assert summary["latest_transition_allowed"] is True
    assert summary["latest_action_id"] == "inspect_dashboard"


def test_cortex_transition_clamps_confidence(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_transition(
        profile,
        current_state=_state(confidence=0.9),
        action_context={
            "action_id": "increase_confidence",
            "confidence_delta": 0.5,
        },
    )

    record = payload["transition_records"][0]
    assert record["predicted_average_confidence"] == 1.0


def test_cortex_transition_blocks_invalid_source_and_horizon(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    state = _state()
    state["state_allowed"] = False

    payload = build_cortex_transition(
        profile,
        current_state=state,
        action_context={"action_id": "bad_transition"},
        horizon_steps=0,
    )

    record = payload["transition_records"][0]
    assert record["transition_allowed"] is False
    assert "current_state_not_allowed" in record["blockers"]
    assert "horizon_steps_out_of_range" in record["blockers"]
    assert record["next_action"] == "repair_transition_prediction"


def test_cortex_transition_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    kwargs = {
        "current_state": _state(),
        "action_context": {"action_id": "hold"},
    }

    first = build_cortex_transition(profile, **kwargs)
    second = build_cortex_transition(profile, **kwargs)

    assert first["transition_count"] == 1
    assert second["transition_count"] == 1
    first_hash = first["transition_records"][0]["transition_hash"]
    second_hash = second["transition_records"][0]["transition_hash"]
    assert first_hash == second_hash


def _state(*, confidence: float = 0.8) -> dict[str, object]:
    return {
        "state_allowed": True,
        "state_hash": "state-hash",
        "capabilities": ["screen_vision"],
        "average_confidence": confidence,
    }
