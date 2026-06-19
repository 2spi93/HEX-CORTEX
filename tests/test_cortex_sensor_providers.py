from hex_cortex.memory.cortex_sensor_providers import get_cortex_sensor_provider
from hex_cortex.memory.cortex_sensor_providers import list_cortex_sensor_providers
from hex_cortex.memory.cortex_sensor_providers import score_cortex_sensor_provider


def test_sensor_providers_include_expected_candidates() -> None:
    rows = list_cortex_sensor_providers()
    ids = {row["provider_id"] for row in rows}

    assert "browser_display" in ids
    assert "browser_camera" in ids
    assert "browser_microphone" in ids
    assert "browser_speech_output" in ids
    assert "local_image_file" in ids
    assert "local_transcript" in ids


def test_browser_camera_requires_explicit_permission() -> None:
    payload = get_cortex_sensor_provider("browser_camera")

    assert payload["state"] == "candidate"
    assert payload["permission_mode"] == "explicit_user_permission"
    assert payload["secure_context_required"] is True
    assert payload["raw_input_persistence_allowed"] is False


def test_sensor_provider_readiness_score() -> None:
    payload = score_cortex_sensor_provider("browser_display")

    assert payload["ready"] is True
    assert payload["score"] == 100.0
    assert payload["checks"]["permission_declared"] is True
    assert payload["checks"]["raw_persistence_blocked"] is True


def test_unknown_sensor_provider_blocks() -> None:
    payload = get_cortex_sensor_provider("unknown")
    score = score_cortex_sensor_provider("unknown")

    assert payload["state"] == "blocked"
    assert payload["blocker"] == "unknown_sensor_provider"
    assert score["ready"] is False
    assert score["score"] == 0.0
