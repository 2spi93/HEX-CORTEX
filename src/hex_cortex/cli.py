"""Command-line interface for HEX-CORTEX."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from hex_cortex.core.cortex_pipeline import CortexPipeline, CortexPipelineResult
from hex_cortex.core.schemas import Task
from hex_cortex.evolver.pruning import PruningEngine
from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.evolver.skill_library import SkillLibrary
from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
    MemoryConfidenceUpdater,
)
from hex_cortex.memory.index_hydrator import MemoryIndexHydrator
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.profile_health import ProfileHealthScorer
from hex_cortex.memory.profile_health_history import (
    ProfileHealthHistoryJsonlStore,
    ProfileHealthHistoryRecord,
)
from hex_cortex.memory.pruning_application import MemoryPruningApplication
from hex_cortex.memory.pruning_audit import (
    PruningAuditJsonlStore,
    PruningAuditRecord,
)
from hex_cortex.memory.schemas import MemoryRecord
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


@dataclass(frozen=True)
class ProfilePaths:
    """Resolved local profile paths."""

    profile: Path | None
    spine_jsonl: Path | None
    memory_jsonl: Path | None
    skills_jsonl: Path | None


def build_parser() -> argparse.ArgumentParser:
    """Build the HEX-CORTEX CLI parser."""

    parser = argparse.ArgumentParser(
        prog="hex-cortex",
        description="Run one local HEX-CORTEX pipeline pass.",
    )
    parser.add_argument(
        "content",
        nargs="?",
        help="Task content to send into HEX-CORTEX.",
    )
    parser.add_argument(
        "--domain",
        action="append",
        default=[],
        dest="domains",
        help="Domain hint. Can be passed multiple times.",
    )
    parser.add_argument("--novelty", type=float, default=0.5)
    parser.add_argument("--risk", type=float, default=0.5)
    parser.add_argument("--uncertainty", type=float, default=0.5)
    parser.add_argument("--latency-budget-ms", type=int, default=2_000)
    parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="Local profile directory for spine, memory, and skills JSONL files.",
    )
    parser.add_argument(
        "--spine-jsonl",
        type=Path,
        default=None,
        help="Optional JSONL path used to load and persist canonical spine events.",
    )
    parser.add_argument(
        "--memory-jsonl",
        type=Path,
        default=None,
        help="Optional JSONL path used to load and append consolidated memories.",
    )
    parser.add_argument(
        "--skills-jsonl",
        type=Path,
        default=None,
        help="Optional JSONL path used to load active procedural skills.",
    )
    parser.add_argument(
        "--bootstrap-skill",
        type=Path,
        default=None,
        help="Append one validated SkillRecord to the given skills JSONL path.",
    )
    parser.add_argument(
        "--inspect-profile",
        type=Path,
        default=None,
        help="Inspect a profile directory without running a task.",
    )
    parser.add_argument(
        "--profile-health",
        type=Path,
        default=None,
        help="Score local profile health without running a task.",
    )
    parser.add_argument(
        "--record-profile-health",
        type=Path,
        default=None,
        help="Record local profile health into profile-health JSONL.",
    )
    parser.add_argument(
        "--confirm-memory-profile",
        type=Path,
        default=None,
        help="Confirm one profile memory and increase its confidence.",
    )
    parser.add_argument(
        "--confirm-memory-id",
        default=None,
        help="Memory id to confirm with --confirm-memory-profile.",
    )
    parser.add_argument(
        "--confirm-memory-reason",
        default="operator_confirmed",
        help="Reason recorded for explicit memory confirmation.",
    )
    parser.add_argument(
        "--confirm-memory-delta",
        type=float,
        default=0.05,
        help="Confidence increase used by --confirm-memory-profile.",
    )
    parser.add_argument(
        "--inspect-spine",
        type=Path,
        default=None,
        help="Inspect a canonical spine JSONL file without running a task.",
    )
    parser.add_argument(
        "--inspect-memory",
        type=Path,
        default=None,
        help="Inspect a memory JSONL file without running a task.",
    )
    parser.add_argument(
        "--inspect-memory-records",
        type=Path,
        default=None,
        help="Inspect memory records with ids and confidence metadata.",
    )
    parser.add_argument(
        "--inspect-skills",
        type=Path,
        default=None,
        help="Inspect a skills JSONL file without running a task.",
    )
    parser.add_argument(
        "--prune-memory-profile",
        type=Path,
        default=None,
        help="Dry-run memory pruning for a profile without mutating files.",
    )
    parser.add_argument(
        "--apply-memory-pruning-profile",
        type=Path,
        default=None,
        help="Apply memory pruning for a profile after writing a backup.",
    )
    parser.add_argument(
        "--restore-memory-pruning-profile",
        type=Path,
        default=None,
        help="Restore profile memory from the pruning backup file.",
    )
    parser.add_argument("--skill-name", default=None, help="Skill name for bootstrap mode.")
    parser.add_argument(
        "--skill-description",
        default=None,
        help="Skill description for bootstrap mode.",
    )
    parser.add_argument(
        "--skill-trigger",
        action="append",
        default=[],
        dest="skill_triggers",
        help="Skill trigger tag. Can be passed multiple times.",
    )
    parser.add_argument(
        "--skill-step",
        action="append",
        default=[],
        dest="skill_steps",
        help="Skill workflow step. Can be passed multiple times.",
    )
    parser.add_argument("--skill-confidence", type=float, default=0.8)
    parser.add_argument(
        "--skill-status",
        choices=[status.value for status in SkillStatus],
        default=SkillStatus.ACTIVE.value,
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def summarize_result(
    result: CortexPipelineResult,
    *,
    persisted_event_count: int | None = None,
    persisted_memory_count: int | None = None,
    hydrated_memory_count: int | None = None,
    hydrated_skill_count: int | None = None,
    profile_path: str | None = None,
) -> dict[str, object]:
    """Convert a pipeline result into stable CLI JSON."""

    decision = result.routing_decision
    payload: dict[str, object] = {
        "task_id": result.task_id,
        "mode": decision.mode.value,
        "selected_cells": decision.selected_cells,
        "retrieval_method": result.context_packet.method.value,
        "retrieval_result_count": len(result.context_packet.results),
        "matched_skill_count": len(result.matched_skills),
        "replay_status": result.replay_report.status.value,
        "pruning_decisions": len(result.pruning_report.decisions),
        "clock_completed": result.clock_completed,
    }
    if profile_path is not None:
        payload["profile_path"] = profile_path
    if persisted_event_count is not None:
        payload["persisted_event_count"] = persisted_event_count
    if persisted_memory_count is not None:
        payload["persisted_memory_count"] = persisted_memory_count
    if hydrated_memory_count is not None:
        payload["hydrated_memory_count"] = hydrated_memory_count
    if hydrated_skill_count is not None:
        payload["hydrated_skill_count"] = hydrated_skill_count
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process-style exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    inspect_payload = _inspect_payload(args)
    if inspect_payload is not None:
        _write_json(inspect_payload, pretty=args.pretty)
        return 0

    health_payload = _health_payload(args)
    if health_payload is not None:
        _write_json(health_payload, pretty=args.pretty)
        return 0

    memory_confidence_payload = _memory_confidence_payload(args)
    if memory_confidence_payload is not None:
        _write_json(memory_confidence_payload, pretty=args.pretty)
        return 0

    pruning_payload = _pruning_payload(args)
    if pruning_payload is not None:
        _write_json(pruning_payload, pretty=args.pretty)
        return 0

    if args.bootstrap_skill is not None:
        payload = _bootstrap_skill(args)
        _write_json(payload, pretty=args.pretty)
        return 0

    if args.content is None:
        parser.error(
            "content is required unless an inspect, health, confidence, "
            "pruning, or bootstrap mode is used"
        )

    paths = resolve_profile_paths(args)
    task = Task(
        content=args.content,
        domain_hints=args.domains,
        novelty=args.novelty,
        risk=args.risk,
        uncertainty=args.uncertainty,
        latency_budget_ms=args.latency_budget_ms,
    )

    spine = _load_spine(paths.spine_jsonl)
    index, hydrated_memory_count = _load_memory_index(paths.memory_jsonl)
    skill_library, hydrated_skill_count = _load_skill_library(paths.skills_jsonl)
    result = CortexPipeline(
        spine=spine,
        index=index,
        skill_library=skill_library,
    ).run(task)
    persisted_event_count = _save_spine(paths.spine_jsonl, spine)
    persisted_memory_count = _save_memory(
        paths.memory_jsonl,
        result.replay_report.memory,
    )
    payload = summarize_result(
        result,
        persisted_event_count=persisted_event_count,
        persisted_memory_count=persisted_memory_count,
        hydrated_memory_count=hydrated_memory_count,
        hydrated_skill_count=hydrated_skill_count,
        profile_path=str(paths.profile) if paths.profile is not None else None,
    )
    _write_json(payload, pretty=args.pretty)
    return 0


def resolve_profile_paths(args: argparse.Namespace) -> ProfilePaths:
    """Resolve explicit JSONL paths with optional profile defaults."""

    profile = args.profile
    return ProfilePaths(
        profile=profile,
        spine_jsonl=args.spine_jsonl or _profile_file(profile, "spine.jsonl"),
        memory_jsonl=args.memory_jsonl or _profile_file(profile, "memory.jsonl"),
        skills_jsonl=args.skills_jsonl or _profile_file(profile, "skills.jsonl"),
    )


def _profile_file(profile: Path | None, filename: str) -> Path | None:
    if profile is None:
        return None
    return profile / filename


def _inspect_payload(args: argparse.Namespace) -> dict[str, object] | None:
    modes = [
        args.inspect_profile is not None,
        args.inspect_spine is not None,
        args.inspect_memory is not None,
        args.inspect_memory_records is not None,
        args.inspect_skills is not None,
    ]
    if sum(modes) > 1:
        raise ValueError("only one inspect mode can be used at a time")
    if args.inspect_profile is not None:
        return inspect_profile(args.inspect_profile)
    if args.inspect_spine is not None:
        return inspect_spine(args.inspect_spine)
    if args.inspect_memory is not None:
        return inspect_memory(args.inspect_memory)
    if args.inspect_memory_records is not None:
        return inspect_memory_records(args.inspect_memory_records)
    if args.inspect_skills is not None:
        return inspect_skills(args.inspect_skills)
    return None


def _health_payload(args: argparse.Namespace) -> dict[str, object] | None:
    modes = [
        args.profile_health is not None,
        args.record_profile_health is not None,
    ]
    if sum(modes) > 1:
        raise ValueError("only one health mode can be used at a time")
    if args.profile_health is not None:
        return profile_health(args.profile_health)
    if args.record_profile_health is not None:
        return record_profile_health(args.record_profile_health)
    return None


def _memory_confidence_payload(args: argparse.Namespace) -> dict[str, object] | None:
    if args.confirm_memory_profile is None:
        return None
    if not args.confirm_memory_id:
        raise ValueError("--confirm-memory-id is required with --confirm-memory-profile")
    return confirm_memory_profile(
        args.confirm_memory_profile,
        memory_id=args.confirm_memory_id,
        reason=args.confirm_memory_reason,
        delta=args.confirm_memory_delta,
    )


def _pruning_payload(args: argparse.Namespace) -> dict[str, object] | None:
    modes = [
        args.prune_memory_profile is not None,
        args.apply_memory_pruning_profile is not None,
        args.restore_memory_pruning_profile is not None,
    ]
    if sum(modes) > 1:
        raise ValueError("only one pruning mode can be used at a time")
    if args.prune_memory_profile is not None:
        return prune_memory_profile(args.prune_memory_profile)
    if args.apply_memory_pruning_profile is not None:
        return apply_memory_pruning_profile(args.apply_memory_pruning_profile)
    if args.restore_memory_pruning_profile is not None:
        return restore_memory_pruning_profile(args.restore_memory_pruning_profile)
    return None


def inspect_profile(profile: Path) -> dict[str, object]:
    """Inspect all standard JSONL files in a profile directory."""

    spine_path = profile / "spine.jsonl"
    memory_path = profile / "memory.jsonl"
    skills_path = profile / "skills.jsonl"
    pruning_audit_path = profile / "pruning-audit.jsonl"
    health_history_path = profile / "profile-health.jsonl"
    confidence_audit_path = profile / "memory-confidence-audit.jsonl"
    pruning = memory_pruning_summary(profile)
    return {
        "inspect_type": "profile",
        "path": str(profile),
        "exists": profile.exists(),
        "spine": inspect_spine(spine_path),
        "memory": inspect_memory(memory_path),
        "skills": inspect_skills(skills_path),
        "memory_pruning": pruning,
        "pruning_audit": inspect_pruning_audit(pruning_audit_path),
        "memory_confidence_audit": inspect_memory_confidence_audit(
            confidence_audit_path
        ),
        "profile_health": profile_health(profile),
        "profile_health_history": inspect_profile_health_history(health_history_path),
    }


def profile_health(profile: Path) -> dict[str, object]:
    """Score local profile health without mutating files."""

    return ProfileHealthScorer(profile).score().model_dump(mode="json")


def record_profile_health(profile: Path) -> dict[str, object]:
    """Record profile health into a local JSONL history."""

    history_path = profile / "profile-health.jsonl"
    report = ProfileHealthScorer(profile).score()
    record = ProfileHealthHistoryRecord.from_report(report)
    store = ProfileHealthHistoryJsonlStore(history_path)
    history_count = store.append(record)
    summary = store.summarize()
    return {
        "record_type": "profile_health",
        "profile_path": str(profile),
        "history_path": str(history_path),
        "history_id": record.history_id,
        "history_record_count": history_count,
        "overall_score": record.overall_score,
        "status": record.status,
        "trend": summary.trend,
        "score_delta": summary.score_delta,
        "latest_score": summary.latest_score,
        "previous_score": summary.previous_score,
    }


def confirm_memory_profile(
    profile: Path,
    *,
    memory_id: str,
    reason: str,
    delta: float,
) -> dict[str, object]:
    """Confirm one memory in a profile and audit the confidence update."""

    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory_store = LocalMemoryJsonlStore(memory_path)
    memories = memory_store.load()
    updated_memories, report = MemoryConfidenceUpdater(delta=delta).confirm(
        memories,
        memory_id=memory_id,
        reason=reason,
    )
    if not report.found:
        return {
            "confirm_type": "memory_profile",
            "confirmed": False,
            "profile_path": str(profile),
            "memory_path": str(memory_path),
            "memory_id": memory_id,
            "reason": reason,
            "changed": False,
            "audit_written": False,
        }

    memory_store.save(updated_memories)
    audit_record = MemoryConfidenceAuditRecord(
        memory_id=memory_id,
        reason=reason,
        before_confidence=report.before_confidence or 0.0,
        after_confidence=report.after_confidence or 0.0,
        delta=report.delta,
        changed=report.changed,
        before_access_count=report.before_access_count or 0,
        after_access_count=report.after_access_count or 0,
    )
    audit_count = MemoryConfidenceAuditJsonlStore(audit_path).append(audit_record)
    return {
        "confirm_type": "memory_profile",
        "confirmed": True,
        "profile_path": str(profile),
        "memory_path": str(memory_path),
        "audit_path": str(audit_path),
        "audit_id": audit_record.audit_id,
        "audit_record_count": audit_count,
        "memory_id": memory_id,
        "reason": reason,
        "changed": report.changed,
        "before_confidence": report.before_confidence,
        "after_confidence": report.after_confidence,
        "delta": report.delta,
        "before_access_count": report.before_access_count,
        "after_access_count": report.after_access_count,
        "audit_written": True,
    }


def inspect_profile_health_history(path: Path) -> dict[str, object]:
    """Inspect profile health history without recording a new snapshot."""

    store = ProfileHealthHistoryJsonlStore(path)
    summary = store.summarize()
    return {
        "inspect_type": "profile_health_history",
        "path": str(path),
        "exists": path.exists(),
        "total_history_count": summary.total_history_count,
        "latest_score": summary.latest_score,
        "previous_score": summary.previous_score,
        "score_delta": summary.score_delta,
        "trend": summary.trend,
        "latest_status": summary.latest_status,
    }


def inspect_memory_confidence_audit(path: Path) -> dict[str, object]:
    """Inspect memory confidence audit records."""

    records = MemoryConfidenceAuditJsonlStore(path).load()
    latest = records[-1] if records else None
    return {
        "inspect_type": "memory_confidence_audit",
        "path": str(path),
        "exists": path.exists(),
        "total_audit_count": len(records),
        "latest_audit_id": latest.audit_id if latest else None,
        "latest_memory_id": latest.memory_id if latest else None,
        "latest_reason": latest.reason if latest else None,
        "latest_delta": latest.delta if latest else None,
    }


def inspect_spine(path: Path) -> dict[str, object]:
    spine = CanonicalSpineJsonlStore(path).load()
    projection = spine.project()
    integrity = spine.verify_integrity()
    return {
        "inspect_type": "spine",
        "path": str(path),
        "exists": path.exists(),
        "integrity_ok": integrity.ok,
        "checked_events": integrity.checked_events,
        "integrity_reason": integrity.reason,
        "total_events": projection.total_events,
        "task_count": projection.task_count,
        "event_type_counts": projection.event_type_counts,
        "latest_sequence_number": projection.latest_sequence_number,
        "latest_event_hash": projection.latest_event_hash,
    }


def inspect_memory(path: Path) -> dict[str, object]:
    store = LocalMemoryJsonlStore(path)
    records = store.load()
    total_count = len(records)
    visible_count = sum(1 for record in records if record.visible)
    tag_counts = Counter(tag for record in records for tag in record.tags)
    type_counts = Counter(record.memory_type.value for record in records)
    average_confidence = (
        round(sum(record.confidence for record in records) / total_count, 4)
        if total_count
        else 0.0
    )
    return {
        "inspect_type": "memory",
        "path": str(path),
        "exists": path.exists(),
        "total_memory_count": total_count,
        "visible_memory_count": visible_count,
        "hidden_memory_count": total_count - visible_count,
        "average_confidence": average_confidence,
        "access_count_total": sum(record.access_count for record in records),
        "tag_counts": dict(sorted(tag_counts.items())),
        "memory_type_counts": dict(sorted(type_counts.items())),
    }


def inspect_memory_records(path: Path) -> dict[str, object]:
    """Inspect memory records with stable identifiers."""

    records = LocalMemoryJsonlStore(path).load()
    return {
        "inspect_type": "memory_records",
        "path": str(path),
        "exists": path.exists(),
        "total_memory_count": len(records),
        "records": [
            {
                "memory_id": record.memory_id,
                "title": record.title,
                "memory_type": record.memory_type.value,
                "confidence": record.confidence,
                "visible": record.visible,
                "access_count": record.access_count,
                "last_accessed_at": record.last_accessed_at,
                "tags": record.tags,
            }
            for record in records
        ],
    }


def inspect_skills(path: Path) -> dict[str, object]:
    records = SkillJsonlStore(path).load()
    status_counts = Counter(skill.status.value for skill in records)
    return {
        "inspect_type": "skills",
        "path": str(path),
        "exists": path.exists(),
        "total_skill_count": len(records),
        "active_skill_count": status_counts.get(SkillStatus.ACTIVE.value, 0),
        "candidate_skill_count": status_counts.get(SkillStatus.CANDIDATE.value, 0),
        "degraded_skill_count": status_counts.get(SkillStatus.DEGRADED.value, 0),
        "archived_skill_count": status_counts.get(SkillStatus.ARCHIVED.value, 0),
        "status_counts": dict(sorted(status_counts.items())),
    }


def inspect_pruning_audit(path: Path) -> dict[str, object]:
    records = PruningAuditJsonlStore(path).load()
    operation_counts = Counter(record.operation for record in records)
    latest = records[-1] if records else None
    return {
        "inspect_type": "pruning_audit",
        "path": str(path),
        "exists": path.exists(),
        "total_audit_count": len(records),
        "operation_counts": dict(sorted(operation_counts.items())),
        "latest_audit_id": latest.audit_id if latest else None,
        "latest_operation": latest.operation if latest else None,
    }


def memory_pruning_summary(profile: Path) -> dict[str, object]:
    payload = _memory_pruning_payload(profile, dry_run=True, audit=False)
    return {
        "dry_run": True,
        "changed_count": payload["changed_count"],
        "archive_count": payload["archive_count"],
        "degrade_count": payload["degrade_count"],
        "keep_count": payload["keep_count"],
        "visible_before": payload["visible_before"],
        "visible_after": payload["visible_after"],
    }


def prune_memory_profile(profile: Path) -> dict[str, object]:
    """Dry-run memory pruning for one local profile."""

    return _memory_pruning_payload(profile, dry_run=True, audit=True)


def apply_memory_pruning_profile(profile: Path) -> dict[str, object]:
    """Apply memory pruning for one local profile after backup."""

    return _memory_pruning_payload(profile, dry_run=False, audit=True)


def restore_memory_pruning_profile(profile: Path) -> dict[str, object]:
    """Restore profile memory from the pruning backup file."""

    memory_path = profile / "memory.jsonl"
    backup_path = profile / "memory.prune-backup.jsonl"
    current_records = LocalMemoryJsonlStore(memory_path).load()
    backup_records = LocalMemoryJsonlStore(backup_path).load()
    restored_count = LocalMemoryJsonlStore(memory_path).save(backup_records)
    visible_before = sum(1 for memory in current_records if memory.visible)
    visible_after = sum(1 for memory in backup_records if memory.visible)
    payload: dict[str, object] = {
        "restore_type": "memory_pruning_profile",
        "restored": True,
        "dry_run": False,
        "applied": True,
        "profile_path": str(profile),
        "memory_path": str(memory_path),
        "backup_path": str(backup_path),
        "restored_memory_count": restored_count,
        "visible_memory_count": visible_after,
        "total_memory_count": restored_count,
        "changed_count": abs(visible_after - visible_before),
        "visible_before": visible_before,
        "visible_after": visible_after,
        "keep_count": restored_count,
        "degrade_count": 0,
        "archive_count": 0,
    }
    payload.update(_append_pruning_audit(profile, "restore", payload))
    return payload


def _memory_pruning_payload(
    profile: Path,
    *,
    dry_run: bool,
    audit: bool,
) -> dict[str, object]:
    memory_path = profile / "memory.jsonl"
    backup_path = profile / "memory.prune-backup.jsonl"
    store = LocalMemoryJsonlStore(memory_path)
    memories = store.load()
    decisions = PruningEngine().decide_batch(memories=memories)
    application = MemoryPruningApplication(memories).apply(decisions, dry_run=dry_run)
    backup_written = False
    persisted_memory_count = len(memories)
    if not dry_run:
        LocalMemoryJsonlStore(backup_path).save(memories)
        persisted_memory_count = store.save(application.memories)
        backup_written = True
    payload: dict[str, object] = {
        "prune_type": "memory_profile",
        "dry_run": dry_run,
        "applied": not dry_run,
        "backup_written": backup_written,
        "backup_path": str(backup_path) if backup_written else None,
        "profile_path": str(profile),
        "memory_path": str(memory_path),
        "persisted_memory_count": persisted_memory_count,
        "total_memory_count": application.total_memory_count,
        "decision_count": application.decision_count,
        "changed_count": application.changed_count,
        "visible_before": application.visible_before,
        "visible_after": application.visible_after,
        "keep_count": decisions.keep_count,
        "degrade_count": decisions.degrade_count,
        "archive_count": decisions.archive_count,
        "changes": [change.model_dump(mode="json") for change in application.changes],
    }
    if audit:
        operation = "preview" if dry_run else "apply"
        payload.update(_append_pruning_audit(profile, operation, payload))
    return payload


def _append_pruning_audit(
    profile: Path,
    operation: str,
    payload: dict[str, object],
) -> dict[str, object]:
    audit_path = profile / "pruning-audit.jsonl"
    record = PruningAuditRecord(
        operation=operation,
        profile_path=str(profile),
        memory_path=str(payload["memory_path"]),
        backup_path=payload.get("backup_path"),
        dry_run=bool(payload["dry_run"]),
        applied=bool(payload["applied"]),
        total_memory_count=int(payload["total_memory_count"]),
        changed_count=int(payload["changed_count"]),
        visible_before=int(payload["visible_before"]),
        visible_after=int(payload["visible_after"]),
        keep_count=int(payload["keep_count"]),
        degrade_count=int(payload["degrade_count"]),
        archive_count=int(payload["archive_count"]),
    )
    audit_count = PruningAuditJsonlStore(audit_path).append(record)
    return {
        "audit_id": record.audit_id,
        "audit_path": str(audit_path),
        "audit_record_count": audit_count,
    }


def _bootstrap_skill(args: argparse.Namespace) -> dict[str, object]:
    if not args.skill_name:
        raise ValueError("--skill-name is required with --bootstrap-skill")

    description = args.skill_description or f"Reusable workflow for {args.skill_name}."
    triggers = args.skill_triggers or [args.skill_name]
    steps = args.skill_steps or ["inspect", "act", "verify"]
    skill = SkillRecord(
        name=args.skill_name,
        description=description,
        trigger_tags=triggers,
        workflow_steps=steps,
        confidence=args.skill_confidence,
        status=SkillStatus(args.skill_status),
    )
    total_count = SkillJsonlStore(args.bootstrap_skill).append(skill)
    active_count = len(SkillJsonlStore(args.bootstrap_skill).active())
    return {
        "bootstrapped_skill_count": total_count,
        "active_skill_count": active_count,
        "skill_id": skill.skill_id,
        "skill_name": skill.name,
        "skill_status": skill.status.value,
        "skill_trigger_count": len(skill.trigger_tags),
        "skill_step_count": len(skill.workflow_steps),
        "skills_path": str(args.bootstrap_skill),
    }


def _write_json(payload: dict[str, object], *, pretty: bool) -> None:
    indent = 2 if pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")


def _load_spine(path: Path | None) -> CanonicalSpine:
    if path is None:
        return CanonicalSpine()
    return CanonicalSpineJsonlStore(path).load()


def _load_memory_index(path: Path | None) -> tuple[LocalKnowledgeIndex, int | None]:
    index = LocalKnowledgeIndex()
    if path is None:
        return index, None
    memories = LocalMemoryJsonlStore(path).visible()
    hydrated_count = MemoryIndexHydrator(index).hydrate(memories)
    return index, hydrated_count


def _load_skill_library(path: Path | None) -> tuple[SkillLibrary, int | None]:
    if path is None:
        return SkillLibrary(), None
    skills = SkillJsonlStore(path).active()
    return SkillLibrary(skills), len(skills)


def _save_spine(path: Path | None, spine: CanonicalSpine) -> int | None:
    if path is None:
        return None
    return CanonicalSpineJsonlStore(path).save(spine)


def _save_memory(path: Path | None, memory: MemoryRecord | None) -> int | None:
    if path is None:
        return None
    if memory is None:
        return len(LocalMemoryJsonlStore(path).load())
    return LocalMemoryJsonlStore(path).append(memory)


if __name__ == "__main__":
    raise SystemExit(main())
