from datetime import UTC, datetime, timedelta

import pytest

from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore
from hex_cortex.memory.confidence_decay import (
    MemoryConfidenceDecayPlanner,
    run_memory_confidence_decay_profile,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def timestamp_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def test_memory_confidence_decay_plan_detects_stale_memory() -> None:
    stale = MemoryRecord(
        title="stale",
        body="body",
        confidence=0.8,
        access_count=2,
        last_accessed_at=timestamp_days_ago(45),
    )
    recent = MemoryRecord(
        title="recent",
        body="body",
        confidence=0.8,
        access_count=2,
        last_accessed_at=timestamp_days_ago(5),
    )
    undated = MemoryRecord(title="undated", body="body", confidence=0.8)

    plan = MemoryConfidenceDecayPlanner(stale_after_days=30).plan(
        [stale, recent, undated],
        limit=5,
    )

    assert plan.total_memory_count == 3
    assert plan.visible_memory_count == 3
    assert plan.stale_memory_count == 1
    assert plan.candidate_count == 1
    assert plan.candidates[0].memory_id == stale.memory_id
    assert plan.candidates[0].after_confidence == 0.75
    assert plan.candidates[0].reason == "stale_memory_confidence_decay"


def test_memory_confidence_decay_respects_minimum_confidence() -> None:
    memory = MemoryRecord(
        title="floor",
        body="body",
        confidence=0.32,
        access_count=1,
        last_accessed_at=timestamp_days_ago(60),
    )

    plan = MemoryConfidenceDecayPlanner(
        stale_after_days=30,
        decay_amount=0.05,
        minimum_confidence=0.3,
    ).plan([memory], limit=1)

    assert plan.candidate_count == 1
    assert plan.candidates[0].after_confidence == 0.3
    assert plan.candidates[0].decay_amount == 0.02


def test_memory_confidence_decay_dry_run_does_not_mutate_or_audit(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(
        title="stale",
        body="body",
        confidence=0.8,
        access_count=1,
        last_accessed_at=timestamp_days_ago(60),
    )
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = run_memory_confidence_decay_profile(profile, dry_run=True)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]

    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert payload["candidate_count"] == 1
    assert payload["decayed_count"] == 1
    assert payload["audit_records_written"] == 0
    assert persisted.confidence == 0.8
    assert not audit_path.exists()


def test_memory_confidence_decay_apply_mutates_and_writes_negative_audit(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(
        title="stale",
        body="body",
        confidence=0.8,
        access_count=1,
        last_accessed_at=timestamp_days_ago(60),
    )
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = run_memory_confidence_decay_profile(
        profile,
        dry_run=False,
        stale_after_days=30,
    )
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert payload["dry_run"] is False
    assert payload["applied"] is True
    assert payload["audit_records_written"] == 1
    assert persisted.confidence == 0.75
    assert audits[0].reason == "stale_memory_confidence_decay"
    assert audits[0].delta == -0.05


def test_memory_confidence_decay_rejects_invalid_config() -> None:
    with pytest.raises(ValueError, match="stale_after_days"):
        MemoryConfidenceDecayPlanner(stale_after_days=-1)
    with pytest.raises(ValueError, match="decay_amount"):
        MemoryConfidenceDecayPlanner(decay_amount=0)
    with pytest.raises(ValueError, match="minimum_confidence"):
        MemoryConfidenceDecayPlanner(minimum_confidence=2)
