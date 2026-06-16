import json

from hex_cortex.cli import main
from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
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


def test_cli_profile_health_outputs_score(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    populate_profile(profile)

    exit_code = main(["--profile-health", str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["profile_path"] == str(profile)
    assert payload["status"] == "healthy"
    assert payload["overall_score"] >= 0.95
    assert payload["spine_integrity_ok"] is True
    assert payload["pruning_audit_count"] == 1


def test_cli_inspect_profile_includes_profile_health(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    populate_profile(profile)

    main(["--inspect-profile", str(profile)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["profile_health"]["status"] == "healthy"
    assert payload["profile_health"]["overall_score"] >= 0.95
