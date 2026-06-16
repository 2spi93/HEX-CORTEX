import json

from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.profile_inspect_cli import inspect_profile_plus, main
from hex_cortex.memory.schemas import MemoryRecord


def test_profile_inspect_plus_includes_memory_confidence_plan(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])

    payload = inspect_profile_plus(profile, limit=2)
    plan = payload["memory_confidence_plan"]
    summary = payload["memory_confidence_audit_summary"]

    assert payload["inspect_type"] == "profile"
    assert plan["candidate_count"] == 1
    assert plan["limit"] == 2
    assert plan["saturation_threshold"] == 0.7
    assert plan["unsaturated_memory_count"] == 1
    assert plan["candidates"][0]["memory_id"] == memory.memory_id
    assert plan["candidates"][0]["saturation_state"] == "needs_confirmation"
    assert summary["total_audit_count"] == 0
    assert summary["net_delta"] == 0


def test_profile_inspect_plus_entrypoint_outputs_json(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])

    exit_code = main([str(profile), "--limit", "1", "--pretty"])
    payload = json.loads(capsys.readouterr().out)
    plan = payload["memory_confidence_plan"]

    assert exit_code == 0
    assert plan["candidate_count"] == 1
    assert plan["limit"] == 1


def test_profile_inspect_plus_entrypoint_uses_saturation_threshold(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(
        title="memory",
        body="body",
        confidence=0.65,
        access_count=1,
    )
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])

    exit_code = main([
        str(profile),
        "--saturation-threshold",
        "0.6",
    ])
    payload = json.loads(capsys.readouterr().out)
    plan = payload["memory_confidence_plan"]

    assert exit_code == 0
    assert plan["saturation_threshold"] == 0.6
    assert plan["saturated_memory_count"] == 1
    assert plan["candidate_count"] == 0


def test_profile_inspect_plus_includes_memory_confidence_audit_summary(tmp_path) -> None:
    profile = tmp_path / "profile"
    audit_path = profile / "memory-confidence-audit.jsonl"
    MemoryConfidenceAuditJsonlStore(audit_path).save([
        MemoryConfidenceAuditRecord(
            memory_id="mem_a",
            reason="retrieval_confirmed",
            before_confidence=0.5,
            after_confidence=0.55,
            delta=0.05,
            changed=True,
            before_access_count=0,
            after_access_count=1,
        ),
        MemoryConfidenceAuditRecord(
            memory_id="mem_b",
            reason="stale_memory_confidence_decay",
            before_confidence=0.6,
            after_confidence=0.59,
            delta=-0.01,
            changed=True,
            before_access_count=2,
            after_access_count=2,
        ),
    ])

    payload = inspect_profile_plus(profile)
    summary = payload["memory_confidence_audit_summary"]

    assert summary["total_audit_count"] == 2
    assert summary["positive_delta_count"] == 1
    assert summary["negative_delta_count"] == 1
    assert summary["net_delta"] == 0.04
