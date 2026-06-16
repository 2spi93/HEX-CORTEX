import json

from hex_cortex.memory.profile_inspect_cli import main
from hex_cortex.memory.profile_readiness_snapshot import (
    ProfileReadinessSnapshotJsonlStore,
    ProfileReadinessSnapshotRecord,
)


def test_profile_inspect_cli_outputs_readiness_gate(tmp_path, capsys) -> None:
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

    exit_code = main([
        str(profile),
        "--gate-minimum-ready-score",
        "1.0",
        "--pretty",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["profile_readiness_gate"]["decision"] == "allow"
    assert payload["profile_readiness_gate"]["minimum_ready_score"] == 1.0
