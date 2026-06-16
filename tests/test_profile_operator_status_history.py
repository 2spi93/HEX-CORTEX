from hex_cortex.memory.profile_operator_status_history import (
    ProfileOperatorStatusHistoryJsonlStore,
    ProfileOperatorStatusHistoryRecord,
    record_profile_operator_status_history,
    summarize_profile_operator_status_history,
)
from hex_cortex.memory.profile_readiness_snapshot import (
    ProfileReadinessSnapshotJsonlStore,
    ProfileReadinessSnapshotRecord,
)


def save_readiness_snapshot(profile, verdict: str, score: float) -> None:
    ProfileReadinessSnapshotJsonlStore(profile / "profile-readiness.jsonl").save([
        ProfileReadinessSnapshotRecord(
            profile_path=str(profile),
            verdict=verdict,
            score=score,
            blocked_reasons=[],
            watch_reasons=[],
            readiness_report={"verdict": verdict, "score": score},
        )
    ])


def test_operator_status_history_records_from_latest_snapshot(tmp_path) -> None:
    profile = tmp_path / "profile"
    save_readiness_snapshot(profile, "profile_ready", 1.0)

    payload = record_profile_operator_status_history(profile)
    records = ProfileOperatorStatusHistoryJsonlStore(
        profile / "profile-operator-status.jsonl"
    ).load()

    assert payload["record_type"] == "profile_operator_status_history"
    assert payload["history_count"] == 1
    assert len(records) == 1
    assert records[0].status == "ready"
    assert records[0].decision == "allow"


def test_operator_status_history_summary_handles_missing_and_existing(tmp_path) -> None:
    history_path = tmp_path / "profile-operator-status.jsonl"

    missing = summarize_profile_operator_status_history(history_path)
    assert missing["exists"] is False
    assert missing["total_status_count"] == 0

    store = ProfileOperatorStatusHistoryJsonlStore(history_path)
    store.save([
        ProfileOperatorStatusHistoryRecord(
            profile_path="profile",
            status="ready",
            decision="allow",
            reason="latest_snapshot_ready",
            score=1.0,
            latest_snapshot_id="readiness_a",
        )
    ])

    summary = summarize_profile_operator_status_history(history_path)
    assert summary["exists"] is True
    assert summary["total_status_count"] == 1
    assert summary["latest_status"] == "ready"
    assert summary["latest_decision"] == "allow"


def test_operator_status_history_summary_reports_trend(tmp_path) -> None:
    history_path = tmp_path / "profile-operator-status.jsonl"
    store = ProfileOperatorStatusHistoryJsonlStore(history_path)
    store.save([
        ProfileOperatorStatusHistoryRecord(
            profile_path="profile",
            status="watch",
            decision="watch",
            reason="watch",
            score=0.8,
            latest_snapshot_id="readiness_a",
        ),
        ProfileOperatorStatusHistoryRecord(
            profile_path="profile",
            status="ready",
            decision="allow",
            reason="ready",
            score=1.0,
            latest_snapshot_id="readiness_b",
        ),
    ])

    summary = summarize_profile_operator_status_history(history_path)

    assert summary["previous_status"] == "watch"
    assert summary["latest_status"] == "ready"
    assert summary["score_delta"] == 0.2
    assert summary["status_trend"] == "changed"
