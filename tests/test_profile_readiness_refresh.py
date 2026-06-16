from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_readiness_refresh import refresh_profile_readiness_gate
from hex_cortex.memory.profile_readiness_snapshot import ProfileReadinessSnapshotJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_profile_readiness_refresh_records_snapshot_and_gate(tmp_path) -> None:
    profile = tmp_path / "profile"
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.5)]
    )

    payload = refresh_profile_readiness_gate(profile)
    records = ProfileReadinessSnapshotJsonlStore(profile / "profile-readiness.jsonl").load()

    assert payload["refresh_type"] == "profile_readiness_gate_snapshot_refresh"
    assert payload["snapshot_count"] == 1
    assert payload["decision"] == "block"
    assert payload["reason"] == "latest_snapshot_blocked"
    assert len(records) == 1
    assert records[0].verdict == "profile_blocked"
