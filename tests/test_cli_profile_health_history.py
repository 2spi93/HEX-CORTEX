import json

from hex_cortex.cli import main
from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_health_history import ProfileHealthHistoryJsonlStore
from hex_cortex.memory.pruning_audit import PruningAuditJsonlStore, PruningAuditRecord
from hex_cortex.memory.schemas import MemoryRecord
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def populate_profile(profile) -> None:
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received",
        task_id="task_1",
        source="test",
        payload={"task_id": "task_1"},
    )
    CanonicalSpineJsonlStore(profile / "spine.jsonl").save(spine)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.9)]
    )
    SkillJsonlStore(profile / "skills.jsonl").save(
        [SkillRecord(name="skill", description="Active skill", status=SkillStatus.ACTIVE)]
    )
    PruningAuditJsonlStore(profile / "pruning-audit.jsonl").save(
        [
            PruningAuditRecord(
                operation="apply",
                profile_path=str(profile),
                memory_path=str(profile / "memory.jsonl"),
                backup_path=str(profile / "memory.prune-backup.jsonl"),
                dry_run=False,
                applied=True,
                total_memory_count=1,
                changed_count=0,
                visible_before=1,
                visible_after=1,
                keep_count=1,
                degrade_count=0,
                archive_count=0,
            )
        ]
    )


def test_cli_record_profile_health_appends_history(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    history_path = profile / "profile-health.jsonl"
    populate_profile(profile)

    first_exit = main(["--record-profile-health", str(profile), "--pretty"])
    first_payload = json.loads(capsys.readouterr().out)
    second_exit = main(["--record-profile-health", str(profile)])
    second_payload = json.loads(capsys.readouterr().out)
    records = ProfileHealthHistoryJsonlStore(history_path).load()

    assert first_exit == 0
    assert second_exit == 0
    assert first_payload["history_record_count"] == 1
    assert first_payload["trend"] == "none"
    assert second_payload["history_record_count"] == 2
    assert second_payload["trend"] == "flat"
    assert len(records) == 2


def test_cli_inspect_profile_includes_profile_health_history(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    populate_profile(profile)
    main(["--record-profile-health", str(profile)])
    capsys.readouterr()

    main(["--inspect-profile", str(profile)])
    payload = json.loads(capsys.readouterr().out)
    history = payload["profile_health_history"]

    assert history["total_history_count"] == 1
    assert history["latest_score"] >= 0.95
    assert history["trend"] == "none"
