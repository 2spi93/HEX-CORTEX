from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_operator_status_refresh import refresh_profile_operator_status
from hex_cortex.memory.profile_readiness_snapshot import ProfileReadinessSnapshotJsonlStore
from hex_cortex.memory.schemas import MemoryRecord

EXPECTED_KEYS = {"status", "decision", "reason", "score", "latest_snapshot_id"}


def test_profile_operator_status_refresh_records_snapshot_and_minimal_status(tmp_path) -> None:
    profile = tmp_path / "profile"
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.5)]
    )

    payload = refresh_profile_operator_status(profile)
    records = ProfileReadinessSnapshotJsonlStore(
        profile / "profile-readiness.jsonl"
    ).load()

    assert set(payload) == EXPECTED_KEYS
    assert payload["status"] == "blocked"
    assert payload["decision"] == "block"
    assert payload["reason"] == "latest_snapshot_blocked"
    assert len(records) == 1
    assert records[0].verdict == "profile_blocked"
