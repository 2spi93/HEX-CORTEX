from hex_cortex.memory.cortex_state import CORTEX_STATE_FILENAME
from hex_cortex.memory.cortex_state import build_cortex_state
from hex_cortex.memory.cortex_state import summarize_cortex_state


def test_cortex_state_ready(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    seen_records = [
        {
            "seen_allowed": True,
            "capability_id": "screen_vision",
            "confidence": 0.9,
            "seen_hash": "seen-a",
        },
        {
            "seen_allowed": True,
            "capability_id": "voice_input",
            "confidence": 0.7,
            "seen_hash": "seen-b",
        },
    ]

    payload = build_cortex_state(profile, seen_records=seen_records)

    record = payload["state_records"][0]
    assert record["state_allowed"] is True
    assert record["source_count"] == 2
    assert record["capabilities"] == ["screen_vision", "voice_input"]
    assert record["average_confidence"] == 0.8
    assert record["raw_inputs_saved"] is False
    assert record["next_action"] == "predict_next_state"

    summary = summarize_cortex_state(profile / CORTEX_STATE_FILENAME)
    assert summary["latest_state_allowed"] is True
    assert summary["latest_source_count"] == 2


def test_cortex_state_blocks_without_allowed_records(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_state(
        profile,
        seen_records=[{"seen_allowed": False, "seen_hash": "blocked"}],
    )

    record = payload["state_records"][0]
    assert record["state_allowed"] is False
    assert "no_allowed_seen_records" in record["blockers"]


def test_cortex_state_ignores_blocked_records(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    seen_records = [
        {
            "seen_allowed": True,
            "capability_id": "screen_vision",
            "confidence": 1.0,
            "seen_hash": "seen-a",
        },
        {
            "seen_allowed": False,
            "capability_id": "camera_vision",
            "confidence": 0.1,
            "seen_hash": "blocked",
        },
    ]

    payload = build_cortex_state(profile, seen_records=seen_records)

    record = payload["state_records"][0]
    assert record["source_count"] == 1
    assert record["capabilities"] == ["screen_vision"]
    assert record["average_confidence"] == 1.0
