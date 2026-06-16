from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_health import ProfileHealthScorer, ProfileHealthStatus
from hex_cortex.memory.pruning_audit import PruningAuditJsonlStore, PruningAuditRecord
from hex_cortex.memory.schemas import MemoryRecord
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def populate_healthy_profile(profile) -> None:
    spine = CanonicalSpine()
    spine.append("task.received", {"task_id": "task_1"})
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


def test_profile_health_scores_healthy_profile(tmp_path) -> None:
    profile = tmp_path / "profile"
    populate_healthy_profile(profile)

    report = ProfileHealthScorer(profile).score()

    assert report.status == ProfileHealthStatus.HEALTHY
    assert report.overall_score >= 0.95
    assert report.spine_integrity_ok is True
    assert report.total_events == 1
    assert report.visible_memory_count == 1
    assert report.active_skill_count == 1
    assert report.pruning_audit_count == 1
    assert report.latest_pruning_operation == "apply"


def test_profile_health_penalizes_missing_audit_but_stays_watch(tmp_path) -> None:
    profile = tmp_path / "profile"
    populate_healthy_profile(profile)
    (profile / "pruning-audit.jsonl").unlink()

    report = ProfileHealthScorer(profile).score()

    assert report.status == ProfileHealthStatus.WATCH
    assert report.pruning_audit_count == 0
    assert any(component.name == "audit" for component in report.components)


def test_profile_health_penalizes_hidden_memory(tmp_path) -> None:
    profile = tmp_path / "profile"
    populate_healthy_profile(profile)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="hidden", body="body", confidence=0.9, visible=False)]
    )

    report = ProfileHealthScorer(profile).score()

    assert report.hidden_memory_count == 1
    assert report.pruning_changed_count == 1
    assert report.overall_score < 0.95


def test_profile_health_handles_empty_valid_profile(tmp_path) -> None:
    profile = tmp_path / "profile"

    report = ProfileHealthScorer(profile).score()

    assert report.status in {ProfileHealthStatus.WATCH, ProfileHealthStatus.DEGRADED}
    assert report.total_events == 0
    assert report.total_memory_count == 0
    assert report.total_skill_count == 0
