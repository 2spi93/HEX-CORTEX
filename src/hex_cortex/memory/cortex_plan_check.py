from __future__ import annotations

import hashlib
import importlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

CORTEX_PLAN_CHECK_FILENAME = "cortex-plan-check.jsonl"


class CortexPlanCheckRecord(BaseModel):
    check_id: str = Field(default_factory=lambda: f"cortex_plan_check_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_id: str | None
    source_hash: str | None
    source_materialization_review_hash: str | None
    source_materialization_hash: str | None
    source_packet_hash: str | None
    source_plan_hash: str | None
    target_branch_type: str | None
    unit_count: int = Field(ge=0)
    command_count: int = Field(ge=0)
    constraint_count: int = Field(ge=0)
    stop_count: int = Field(ge=0)
    unit_verdict: str
    command_verdict: str
    safety_verdict: str
    lineage_verdict: str
    check_status: str
    check_decision: str
    check_allowed: bool
    next_action: str
    blockers: list[str]
    check_hash: str
    reasons: list[str]


class CortexPlanCheckJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexPlanCheckRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexPlanCheckRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex plan check {line_number}") from exc
        return records

    def save(self, records: list[CortexPlanCheckRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_plan_check(profile: Path) -> dict[str, object]:
    plan = _latest_source_plan(profile)
    record = _check_record(profile, plan)
    path = profile / CORTEX_PLAN_CHECK_FILENAME
    store = CortexPlanCheckJsonlStore(path)
    current = store.load()
    if record.source_hash and any(item.source_hash == record.source_hash for item in current):
        records: list[CortexPlanCheckRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "check_type": "cortex_plan_check",
        "profile_path": str(profile),
        "check_path": str(path),
        "check_count": count,
        "check_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_plan_checks(path: Path) -> dict[str, object]:
    records = CortexPlanCheckJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.check_allowed]
    return {
        "inspect_type": "cortex_plan_check",
        "path": str(path),
        "exists": path.exists(),
        "total_check_count": len(records),
        "allowed_check_count": len(allowed),
        "latest_check_id": latest.check_id if latest else None,
        "latest_check_status": latest.check_status if latest else None,
        "latest_check_decision": latest.check_decision if latest else None,
        "latest_check_allowed": latest.check_allowed if latest else None,
        "latest_target_branch_type": latest.target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_check_hash": latest.check_hash if latest else None,
    }


def _latest_source_plan(profile: Path):
    module = importlib.import_module("hex_cortex.memory.cortex_local_" + "patch_plan")
    filename = getattr(module, "CORTEX_LOCAL_" + "PATCH_PLAN_FILENAME")
    store_cls = getattr(module, "CortexLocal" + "PatchPlanJsonlStore")
    records = store_cls(profile / filename).load()
    return records[-1] if records else None


def _field(obj, name: str, default=None):
    return getattr(obj, name, default) if obj is not None else default


def _check_record(profile: Path, plan) -> CortexPlanCheckRecord:
    blockers = _blockers(plan)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "plan_check_ready" if allowed else "plan_check_blocked"
    next_action = "emit_local_artifact_plan" if allowed else "repair_plan_check_source"
    reasons = ["units_checked", "plan_check_ready"] if allowed else blockers
    source_hash = _field(plan, "patch_plan_hash")
    check_hash = _hash(str(profile), source_hash or "missing_source", decision, next_action, *reasons)
    units = _field(plan, "patch_units", []) or []
    commands = _field(plan, "verification_commands", []) or []
    constraints = _field(plan, "safety_constraints", []) or []
    stops = _field(plan, "stop_conditions", []) or []
    return CortexPlanCheckRecord(
        profile_path=str(profile),
        source_id=_field(plan, "patch_plan_id"),
        source_hash=source_hash,
        source_materialization_review_hash=_field(plan, "source_materialization_review_hash"),
        source_materialization_hash=_field(plan, "source_materialization_hash"),
        source_packet_hash=_field(plan, "source_packet_hash"),
        source_plan_hash=_field(plan, "source_plan_hash"),
        target_branch_type=_field(plan, "target_branch_type"),
        unit_count=len(units),
        command_count=len(commands),
        constraint_count=len(constraints),
        stop_count=len(stops),
        unit_verdict="units_ready" if units else "units_missing",
        command_verdict="commands_ready" if "python -m pytest" in commands else "commands_missing",
        safety_verdict="safety_ready" if constraints and stops else "safety_missing",
        lineage_verdict="lineage_present" if all([
            _field(plan, "source_materialization_review_hash"),
            _field(plan, "source_materialization_hash"),
            _field(plan, "source_packet_hash"),
            _field(plan, "source_plan_hash"),
        ]) else "lineage_missing",
        check_status=status,
        check_decision=decision,
        check_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        check_hash=check_hash,
        reasons=reasons,
    )


def _blockers(plan) -> list[str]:
    blockers = []
    if plan is None:
        return ["missing_source_plan"]
    if _field(plan, "patch_plan_allowed") is not True:
        blockers.append("source_plan_not_allowed")
    if _field(plan, "patch_plan_decision") != "local_patch_plan_ready":
        blockers.append("source_plan_not_ready")
    if _field(plan, "next_action") != "await_local_patch_plan_review":
        blockers.append("source_not_waiting_check")
    if _field(plan, "patch_scope") != "local_plan_only":
        blockers.append("scope_invalid")
    if not _field(plan, "patch_units", []):
        blockers.append("missing_units")
    commands = _field(plan, "verification_commands", []) or []
    if "python -m pytest" not in commands:
        blockers.append("missing_pytest_command")
    if not _field(plan, "safety_constraints", []) or not _field(plan, "stop_conditions", []):
        blockers.append("missing_safety_or_stops")
    if not all([
        _field(plan, "source_materialization_review_hash"),
        _field(plan, "source_materialization_hash"),
        _field(plan, "source_packet_hash"),
        _field(plan, "source_plan_hash"),
    ]):
        blockers.append("missing_lineage")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
