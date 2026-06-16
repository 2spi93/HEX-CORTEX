from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
)
from hex_cortex.memory.confidence_policy_autosaturation import (
    run_memory_confidence_policy_autosaturation_profile,
)
from hex_cortex.memory.confidence_policy_telemetry import (
    record_memory_confidence_policy_telemetry_profile,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_operational_readiness import (
    inspect_profile_operational_readiness,
)
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
        payload={},
    )
    CanonicalSpineJsonlStore(profile / "spine.jsonl").save(spine)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save(
        [MemoryRecord(title="memory", body="body", confidence=0.9, access_count=1)]
    )
    SkillJsonlStore(profile / "skills.jsonl").save(
        [SkillRecord(name="skill", description="Active skill", status=SkillStatus.ACTIVE)]
    )
    PruningAuditJsonlStore(profile / "pruning-audit.jsonl").save([
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
    ])
    MemoryConfidenceAuditJsonlStore(profile / "memory-confidence-audit.jsonl").save([
        MemoryConfidenceAuditRecord(
            memory_id="mem_a",
            reason="retrieval_confirmed",
            before_confidence=0.85,
            after_confidence=0.9,
            delta=0.05,
            changed=True,
            before_access_count=0,
            after_access_count=1,
        )
    ])


def test_profile_readiness_ready_when_policy_marker_is_stable(tmp_path) -> None:
    profile = tmp_path / "profile"
    populate_profile(profile)
    record_memory_confidence_policy_telemetry_profile(profile)
    run_memory_confidence_policy_autosaturation_profile(
        profile,
        stability_window=1,
        dry_run=False,
    )

    payload = inspect_profile_operational_readiness(profile, policy_stability_window=1)

    assert payload["verdict"] == "profile_ready"
    assert payload["blocked_reasons"] == []
    assert payload["watch_reasons"] == []


def test_profile_readiness_watch_without_stability_history(tmp_path) -> None:
    profile = tmp_path / "profile"
    populate_profile(profile)

    payload = inspect_profile_operational_readiness(profile)

    assert payload["verdict"] == "profile_watch"
    assert "not_enough_policy_telemetry_records" in payload["watch_reasons"]
