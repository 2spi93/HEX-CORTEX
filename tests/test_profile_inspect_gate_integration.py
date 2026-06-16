from hex_cortex.memory.profile_inspect_cli import inspect_profile_plus
from hex_cortex.memory.profile_readiness_snapshot import (
    ProfileReadinessSnapshotJsonlStore,
    ProfileReadinessSnapshotRecord,
)


def test_profile_inspect_plus_includes_readiness_gate(tmp_path) -> None:
    profile = tmp_path / "profile"
    ProfileReadinessSnapshotJsonlStore(profile / "profile-readiness.jsonl").save([
        ProfileReadinessSnapshotRecord(
            profile_path=str(profile),
            verdict="profile_ready",
            score=1.0,
            blocked_reasons=[],
            watch_reasons=[],
            readiness_report={"verdict": "profile_ready", "score": 1.0},
        )
    ])

    payload = inspect_profile_plus(profile)
    gate = payload["profile_readiness_gate"]

    assert gate["gate_type"] == "profile_readiness_gate"
    assert gate["decision"] == "allow"
    assert gate["reason"] == "latest_snapshot_ready"
