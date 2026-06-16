from hex_cortex.memory.profile_readiness_gate import inspect_profile_readiness_gate
from hex_cortex.memory.profile_readiness_snapshot import ProfileReadinessSnapshotJsonlStore
from hex_cortex.memory.profile_readiness_snapshot import ProfileReadinessSnapshotRecord


def save_snapshot(profile, verdict: str, score: float) -> None:
    store = ProfileReadinessSnapshotJsonlStore(profile / "profile-readiness.jsonl")
    store.save([
        ProfileReadinessSnapshotRecord(
            profile_path=str(profile),
            verdict=verdict,
            score=score,
            blocked_reasons=["blocked"] if verdict == "profile_blocked" else [],
            watch_reasons=["watch"] if verdict == "profile_watch" else [],
            readiness_report={"verdict": verdict, "score": score},
        )
    ])


def test_profile_readiness_gate_blocks_when_snapshot_missing(tmp_path) -> None:
    payload = inspect_profile_readiness_gate(tmp_path / "profile")

    assert payload["decision"] == "block"
    assert payload["reason"] == "readiness_snapshot_missing"
    assert payload["snapshot_exists"] is False


def test_profile_readiness_gate_maps_latest_snapshot_to_decision(tmp_path) -> None:
    profile = tmp_path / "profile"
    save_snapshot(profile, "profile_blocked", 0.0)
    blocked = inspect_profile_readiness_gate(profile)
    assert blocked["decision"] == "block"
    assert blocked["reason"] == "latest_snapshot_blocked"

    save_snapshot(profile, "profile_watch", 0.8)
    watched = inspect_profile_readiness_gate(profile)
    assert watched["decision"] == "watch"
    assert watched["reason"] == "latest_snapshot_watch"

    save_snapshot(profile, "profile_ready", 1.0)
    allowed = inspect_profile_readiness_gate(profile)
    assert allowed["decision"] == "allow"
    assert allowed["reason"] == "latest_snapshot_ready"


def test_profile_readiness_gate_watches_ready_score_below_threshold(tmp_path) -> None:
    profile = tmp_path / "profile"
    save_snapshot(profile, "profile_ready", 0.95)

    payload = inspect_profile_readiness_gate(profile, minimum_ready_score=1.0)

    assert payload["decision"] == "watch"
    assert payload["reason"] == "latest_snapshot_score_below_threshold"
