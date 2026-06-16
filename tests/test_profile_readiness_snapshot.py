from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_readiness_snapshot import (
    ProfileReadinessSnapshotJsonlStore,
    ProfileReadinessSnapshotRecord,
    record_profile_readiness_snapshot,
    summarize_profile_readiness_snapshots,
)
from hex_cortex.memory.schemas import MemoryRecord


def test_profile_readiness_snapshot_records_readiness_report(tmp_path) -> None:
    profile = tmp_path / "profile"
    snapshot_path = profile / "profile-readiness.jsonl"
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.5)]
    )

    payload = record_profile_readiness_snapshot(profile)
    records = ProfileReadinessSnapshotJsonlStore(snapshot_path).load()

    assert payload["record_type"] == "profile_readiness_snapshot"
    assert payload["snapshot_count"] == 1
    assert len(records) == 1
    assert records[0].verdict == "profile_blocked"
    assert records[0].readiness_report["readiness_type"] == "profile_operational_readiness"


def test_profile_readiness_snapshot_summary_handles_missing_and_existing(tmp_path) -> None:
    snapshot_path = tmp_path / "profile-readiness.jsonl"

    missing = summarize_profile_readiness_snapshots(snapshot_path)
    assert missing["exists"] is False
    assert missing["total_snapshot_count"] == 0

    store = ProfileReadinessSnapshotJsonlStore(snapshot_path)
    store.save([
        ProfileReadinessSnapshotRecord(
            profile_path="profile",
            verdict="profile_ready",
            score=1.0,
            blocked_reasons=[],
            watch_reasons=[],
            readiness_report={"verdict": "profile_ready"},
        )
    ])

    summary = summarize_profile_readiness_snapshots(snapshot_path)
    assert summary["exists"] is True
    assert summary["total_snapshot_count"] == 1
    assert summary["latest_verdict"] == "profile_ready"
    assert summary["latest_score"] == 1.0


def test_profile_readiness_snapshot_summary_reports_trend(tmp_path) -> None:
    snapshot_path = tmp_path / "profile-readiness.jsonl"
    store = ProfileReadinessSnapshotJsonlStore(snapshot_path)
    store.save([
        ProfileReadinessSnapshotRecord(
            profile_path="profile",
            verdict="profile_watch",
            score=0.8,
            blocked_reasons=[],
            watch_reasons=["watch"],
            readiness_report={"verdict": "profile_watch"},
        ),
        ProfileReadinessSnapshotRecord(
            profile_path="profile",
            verdict="profile_ready",
            score=1.0,
            blocked_reasons=[],
            watch_reasons=[],
            readiness_report={"verdict": "profile_ready"},
        ),
    ])

    summary = summarize_profile_readiness_snapshots(snapshot_path)

    assert summary["previous_verdict"] == "profile_watch"
    assert summary["latest_verdict"] == "profile_ready"
    assert summary["score_delta"] == 0.2
    assert summary["readiness_trend"] == "changed"
