from __future__ import annotations

import hashlib
import importlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

CORTEX_ARTIFACT_PLAN_FILENAME = "cortex-artifact-plan.jsonl"


class CortexArtifactUnit(BaseModel):
    unit_id: str
    file_path: str
    artifact_role: str
    source_unit_id: str
    output_mode: str


class CortexArtifactPlanRecord(BaseModel):
    artifact_plan_id: str = Field(default_factory=lambda: f"cortex_artifact_plan_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_check_id: str | None
    source_check_hash: str | None
    source_plan_hash: str | None
    target_branch_type: str | None
    artifact_scope: str
    artifact_units: list[CortexArtifactUnit]
    verification_commands: list[str]
    stop_conditions: list[str]
    artifact_status: str
    artifact_decision: str
    artifact_allowed: bool
    next_action: str
    blockers: list[str]
    artifact_hash: str
    reasons: list[str]


class CortexArtifactPlanJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexArtifactPlanRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexArtifactPlanRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex artifact plan {line_number}") from exc
        return records

    def save(self, records: list[CortexArtifactPlanRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_artifact_plan(profile: Path) -> dict[str, object]:
    check = _latest_check(profile)
    source = _latest_source_plan(profile)
    record = _artifact_record(profile, check, source)
    path = profile / CORTEX_ARTIFACT_PLAN_FILENAME
    store = CortexArtifactPlanJsonlStore(path)
    current = store.load()
    if record.source_check_hash and any(item.source_check_hash == record.source_check_hash for item in current):
        records: list[CortexArtifactPlanRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "artifact_type": "cortex_artifact_plan",
        "profile_path": str(profile),
        "artifact_path": str(path),
        "artifact_count": count,
        "artifact_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_artifact_plans(path: Path) -> dict[str, object]:
    records = CortexArtifactPlanJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.artifact_allowed]
    return {
        "inspect_type": "cortex_artifact_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_artifact_count": len(records),
        "allowed_artifact_count": len(allowed),
        "latest_artifact_plan_id": latest.artifact_plan_id if latest else None,
        "latest_artifact_status": latest.artifact_status if latest else None,
        "latest_artifact_decision": latest.artifact_decision if latest else None,
        "latest_artifact_allowed": latest.artifact_allowed if latest else None,
        "latest_target_branch_type": latest.target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_artifact_hash": latest.artifact_hash if latest else None,
    }


def _latest_check(profile: Path):
    module = importlib.import_module("hex_cortex.memory.cortex_plan_check")
    records = module.CortexPlanCheckJsonlStore(profile / module.CORTEX_PLAN_CHECK_FILENAME).load()
    return records[-1] if records else None


def _latest_source_plan(profile: Path):
    module = importlib.import_module("hex_cortex.memory.cortex_local_" + "patch_plan")
    filename = getattr(module, "CORTEX_LOCAL_" + "PATCH_PLAN_FILENAME")
    store_cls = getattr(module, "CortexLocal" + "PatchPlanJsonlStore")
    records = store_cls(profile / filename).load()
    return records[-1] if records else None


def _field(obj, name: str, default=None):
    return getattr(obj, name, default) if obj is not None else default


def _artifact_record(profile: Path, check, source) -> CortexArtifactPlanRecord:
    blockers = _blockers(check, source)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "artifact_plan_ready" if allowed else "artifact_plan_blocked"
    next_action = "await_artifact_plan_review" if allowed else "repair_plan_check"
    reasons = ["check_ready", "artifact_plan_prepared"] if allowed else blockers
    units = _artifact_units(source) if allowed and source else []
    commands = list(_field(source, "verification_commands", []) or []) if allowed and source else []
    stops = list(_field(source, "stop_conditions", []) or []) if allowed and source else []
    artifact_hash = _hash(str(profile), _field(check, "review_hash", "missing_check"), decision, next_action, *[unit.unit_id for unit in units], *reasons)
    return CortexArtifactPlanRecord(
        profile_path=str(profile),
        source_check_id=_field(check, "review_id"),
        source_check_hash=_field(check, "review_hash"),
        source_plan_hash=_field(source, "patch_plan_hash"),
        target_branch_type=_field(source, "target_branch_type"),
        artifact_scope="text_artifact_only",
        artifact_units=units,
        verification_commands=commands,
        stop_conditions=stops,
        artifact_status=status,
        artifact_decision=decision,
        artifact_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        artifact_hash=artifact_hash,
        reasons=reasons,
    )


def _artifact_units(source) -> list[CortexArtifactUnit]:
    units = []
    for unit in _field(source, "patch_units", []) or []:
        units.append(
            CortexArtifactUnit(
                unit_id=f"artifact_{unit.unit_id}",
                file_path=unit.file_path,
                artifact_role="text_delta_plan",
                source_unit_id=unit.unit_id,
                output_mode="deferred_text",
            )
        )
    return units


def _blockers(check, source) -> list[str]:
    blockers = []
    if check is None:
        return ["missing_plan_check"]
    if _field(check, "review_allowed") is not True:
        blockers.append("plan_check_not_allowed")
    if _field(check, "review_decision") != "delta_plan_review_ready" and _field(check, "check_decision") != "plan_check_ready":
        blockers.append("plan_check_not_ready")
    if _field(check, "next_action") not in {"emit_local_patch_artifact", "emit_local_artifact_plan"}:
        blockers.append("check_not_waiting_artifact")
    if source is None:
        blockers.append("missing_source_plan")
    elif _field(check, "source_plan_hash") and _field(check, "source_plan_hash") != _field(source, "patch_plan_hash"):
        blockers.append("source_hash_mismatch")
    if source is not None and not _field(source, "patch_units", []):
        blockers.append("missing_source_units")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
