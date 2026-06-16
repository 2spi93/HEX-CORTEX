from hex_cortex.memory.profile_operator_status import inspect_profile_operator_status
from hex_cortex.memory.profile_readiness_snapshot import (
    ProfileReadinessSnapshotJsonlStore,
    ProfileReadinessSnapshotRecord,
)

EXPECTED_KEYS = {"status", "decision", "reason", "score", "latest_snapshot_id"}


def save_snapshot(profile, verdict: str, score: float) -> None:
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


def test_profile_operator_status_blocks_missing_snapshot(tmp_path) -> None:
    payload = inspect_profile_operator_status(tmp_path / "profile")

    assert set(payload) == EXPECTED_KEYS
    assert payload["status"] == "blocked"
    assert payload["decision"] == "block"
    assert payload["reason"] == "readiness_snapshot_missing"
    assert payload["score"] is None
    assert payload["latest_snapshot_id"] is None


def test_profile_operator_status_allows_ready_snapshot(tmp_path) -> None:
    profile = tmp_path / "profile"
    save_snapshot(profile, "profile_ready", 1.0)

    payload = inspect_profile_operator_status(profile)

    assert set(payload) == EXPECTED_KEYS
    assert payload["status"] == "ready"
    assert payload["decision"] == "allow"
    assert payload["reason"] == "latest_snapshot_ready"
    assert payload["score"] == 1.0
    assert payload["latest_snapshot_id"] is not None
