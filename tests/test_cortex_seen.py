from hex_cortex.memory.cortex_seen import CORTEX_SEEN_FILENAME
from hex_cortex.memory.cortex_seen import build_cortex_seen
from hex_cortex.memory.cortex_seen import summarize_cortex_seen


def test_cortex_seen_imports() -> None:
    assert CORTEX_SEEN_FILENAME == "cortex-seen.jsonl"


def test_cortex_seen_ready(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_seen(
        profile,
        provider_id="local_image_file",
        summary="A trading terminal is visible.",
        confidence=0.9,
        approved=True,
    )

    record = payload["seen_records"][0]
    assert record["seen_allowed"] is True
    assert record["capability_id"] == "screen_vision"
    assert record["summary_length"] > 0
    assert isinstance(record["summary_hash"], str)
    assert record["raw_input_saved"] is False
    assert record["raw_output_saved"] is False
    assert record["next_action"] == "build_world_state"

    summary = summarize_cortex_seen(profile / CORTEX_SEEN_FILENAME)
    assert summary["latest_seen_allowed"] is True
    assert summary["latest_provider_id"] == "local_image_file"


def test_cortex_seen_blocks_without_approval(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_seen(
        profile,
        provider_id="local_transcript",
        summary="Operator said hello.",
        confidence=0.8,
        approved=False,
    )

    record = payload["seen_records"][0]
    assert record["seen_allowed"] is False
    assert "approval_required" in record["blockers"]


def test_cortex_seen_blocks_unknown_provider(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_seen(
        profile,
        provider_id="unknown",
        summary="Unknown source.",
        confidence=0.5,
        approved=True,
    )

    record = payload["seen_records"][0]
    assert record["seen_allowed"] is False
    assert "unknown_sensor_provider" in record["blockers"]
