from hex_cortex.memory.cortex_surprise import CORTEX_SURPRISE_FILENAME
from hex_cortex.memory.cortex_surprise import build_cortex_surprise
from hex_cortex.memory.cortex_surprise import summarize_cortex_surprise


def test_cortex_surprise_imports() -> None:
    assert CORTEX_SURPRISE_FILENAME == "cortex-surprise.jsonl"


def test_cortex_surprise_accepts_matching_prediction(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_surprise(
        profile,
        transition_record=_transition(),
        observed_state=_observed(),
    )

    record = payload["prediction_error_records"][0]
    assert record["prediction_error_allowed"] is True
    assert record["missing_expected_capabilities"] == []
    assert record["unexpected_observed_capabilities"] == []
    assert record["capability_error"] == 0.0
    assert record["confidence_error"] == 0.0
    assert record["surprise_score"] == 0.0
    assert record["surprise_level"] == "low"
    assert record["learning_signal"] == "no_update"
    assert record["feature_hash_match"] is True
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["raw_state_persisted"] is False
    assert record["next_action"] == "accept_prediction"

    summary = summarize_cortex_surprise(
        profile / CORTEX_SURPRISE_FILENAME
    )
    assert summary["latest_prediction_error_allowed"] is True
    assert summary["latest_surprise_level"] == "low"


def test_cortex_surprise_detects_high_error(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_surprise(
        profile,
        transition_record=_transition(
            capabilities=["screen_vision", "voice_input"],
            confidence=0.9,
        ),
        observed_state=_observed(
            capabilities=["camera_vision"],
            confidence=0.2,
        ),
    )

    record = payload["prediction_error_records"][0]
    assert record["prediction_error_allowed"] is True
    assert record["missing_expected_capabilities"] == [
        "screen_vision",
        "voice_input",
    ]
    assert record["unexpected_observed_capabilities"] == [
        "camera_vision"
    ]
    assert record["capability_error"] == 1.0
    assert record["confidence_error"] == 0.7
    assert record["surprise_score"] == 0.91
    assert record["surprise_level"] == "high"
    assert record["learning_signal"] == "priority_update"
    assert record["feature_hash_match"] is False
    assert record["next_action"] == "repair_transition_model"


def test_cortex_surprise_blocks_invalid_inputs(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    transition = _transition()
    transition["transition_allowed"] = False
    observed = _observed()
    observed["state_allowed"] = False

    payload = build_cortex_surprise(
        profile,
        transition_record=transition,
        observed_state=observed,
        low_threshold=0.6,
        high_threshold=0.5,
    )

    record = payload["prediction_error_records"][0]
    assert record["prediction_error_allowed"] is False
    assert "transition_not_allowed" in record["blockers"]
    assert "observed_state_not_allowed" in record["blockers"]
    assert "surprise_thresholds_invalid" in record["blockers"]
    assert record["surprise_level"] is None
    assert record["next_action"] == "repair_prediction_error_input"


def test_cortex_surprise_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    kwargs = {
        "transition_record": _transition(),
        "observed_state": _observed(),
    }

    first = build_cortex_surprise(profile, **kwargs)
    second = build_cortex_surprise(profile, **kwargs)

    assert first["prediction_error_count"] == 1
    assert second["prediction_error_count"] == 1
    first_hash = first["prediction_error_records"][0][
        "prediction_error_hash"
    ]
    second_hash = second["prediction_error_records"][0][
        "prediction_error_hash"
    ]
    assert first_hash == second_hash


def _transition(
    *,
    capabilities: list[str] | None = None,
    confidence: float = 0.8,
) -> dict[str, object]:
    return {
        "transition_allowed": True,
        "transition_hash": "transition-hash",
        "predicted_state_hash": "predicted-state-hash",
        "predicted_capabilities": capabilities or ["screen_vision"],
        "predicted_average_confidence": confidence,
    }


def _observed(
    *,
    capabilities: list[str] | None = None,
    confidence: float = 0.8,
) -> dict[str, object]:
    return {
        "state_allowed": True,
        "state_hash": "observed-state-hash",
        "capabilities": capabilities or ["screen_vision"],
        "average_confidence": confidence,
    }
