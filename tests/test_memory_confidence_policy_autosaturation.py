from hex_cortex.memory.confidence_policy_autosaturation import (
    MARKER_FILENAME,
    load_memory_confidence_policy_stability_marker,
    run_memory_confidence_policy_autosaturation_profile,
)
from hex_cortex.memory.confidence_policy_telemetry import (
    record_memory_confidence_policy_telemetry_profile,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_policy_autosaturation_preview_does_not_write_marker(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    marker_path = profile / MARKER_FILENAME
    memory = MemoryRecord(title="memory", body="body", confidence=0.8, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([memory])
    record_memory_confidence_policy_telemetry_profile(profile)

    payload = run_memory_confidence_policy_autosaturation_profile(
        profile,
        stability_window=1,
        dry_run=True,
    )

    assert payload["dry_run"] is True
    assert payload["eligible"] is True
    assert payload["marker_written"] is False
    assert not marker_path.exists()


def test_policy_autosaturation_apply_writes_marker_when_stable(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    marker_path = profile / MARKER_FILENAME
    memory = MemoryRecord(title="memory", body="body", confidence=0.8, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([memory])
    record_memory_confidence_policy_telemetry_profile(profile)

    payload = run_memory_confidence_policy_autosaturation_profile(
        profile,
        stability_window=1,
        dry_run=False,
    )
    marker_payload = load_memory_confidence_policy_stability_marker(profile)

    assert payload["applied"] is True
    assert payload["eligible"] is True
    assert payload["marker_written"] is True
    assert marker_path.exists()
    assert marker_payload["exists"] is True
    assert marker_payload["marker"]["stability_state"] == "confidence_policy_stable"
    assert marker_payload["marker"]["stability_window"] == 1


def test_policy_autosaturation_blocks_and_clears_stale_marker_when_active(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    marker_path = profile / MARKER_FILENAME
    stable_memory = MemoryRecord(title="stable", body="body", confidence=0.8, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([stable_memory])
    record_memory_confidence_policy_telemetry_profile(profile)
    run_memory_confidence_policy_autosaturation_profile(
        profile,
        stability_window=1,
        dry_run=False,
    )
    assert marker_path.exists()

    active_memory = MemoryRecord(title="active", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([active_memory])
    record_memory_confidence_policy_telemetry_profile(profile)
    payload = run_memory_confidence_policy_autosaturation_profile(
        profile,
        stability_window=1,
        dry_run=False,
    )

    assert payload["eligible"] is False
    assert payload["blocked_reason"] == "policy_still_recommends_actions"
    assert payload["stale_marker_cleared"] is True
    assert not marker_path.exists()


def test_policy_stability_marker_inspect_handles_missing_marker(tmp_path) -> None:
    profile = tmp_path / "profile"

    payload = load_memory_confidence_policy_stability_marker(profile)

    assert payload["inspect_type"] == "memory_confidence_policy_stability_marker"
    assert payload["exists"] is False
    assert payload["marker"] is None
