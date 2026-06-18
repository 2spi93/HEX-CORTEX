from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_materialization_plan import (
    CORTEX_MATERIALIZATION_PLAN_FILENAME,
    CortexMaterializationPlanJsonlStore,
    CortexMaterializationPlanRecord,
)
from hex_cortex.memory.cortex_materialization_review_gate import (
    CORTEX_MATERIALIZATION_REVIEW_GATE_FILENAME,
    CortexMaterializationReviewGateJsonlStore,
    CortexMaterializationReviewGateRecord,
)

CORTEX_LOCAL_PATCH_PLAN_FILENAME = "cortex-local-patch-plan.jsonl"


class CortexLocalPatchUnit(BaseModel):
    unit_id: str
    file_path: str
    operation: str
    source_operation: str
    expected_review: str


class CortexLocalPatchPlanRecord(BaseModel):
    patch_plan_id: str = Field(default_factory=lambda: f"cortex_local_patch_plan_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_materialization_review_id: str | None
    source_materialization_review_hash: str | None
    source_materialization_hash: str | None
    source_ack_hash: str | None
    source_packet_hash: str | None
    source_plan_hash: str | None
    target_branch_type: str | None
    patch_scope: str
    patch_units: list[CortexLocalPatchUnit]
    verification_commands: list[str]
    safety_constraints: list[str]
    stop_conditions: list[str]
    patch_plan_status: str
    patch_plan_decision: str
    patch_plan_allowed: bool
    next_action: str
    blockers: list[str]
    patch_plan_hash: str
    reasons: list[str]


class CortexLocalPatchPlanJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexLocalPatchPlanRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexLocalPatchPlanRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex local patch plan {line_number}") from exc
        return records

    def save(self, records: list[CortexLocalPatchPlanRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_local_patch_plan(profile: Path) -> dict[str, object]:
    review = _latest_review(profile)
    materialization = _matching_materialization(profile, review)
    record = _patch_plan_record(profile, review, materialization)
    path = profile / CORTEX_LOCAL_PATCH_PLAN_FILENAME
    store = CortexLocalPatchPlanJsonlStore(path)
    current = store.load()
    if record.source_materialization_review_hash and any(
        item.source_materialization_review_hash == record.source_materialization_review_hash for item in current
    ):
        records: list[CortexLocalPatchPlanRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "patch_plan_type": "cortex_local_patch_plan",
        "profile_path": str(profile),
        "patch_plan_path": str(path),
        "patch_plan_count": count,
        "patch_plan_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_local_patch_plans(path: Path) -> dict[str, object]:
    records = CortexLocalPatchPlanJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.patch_plan_allowed]
    return {
        "inspect_type": "cortex_local_patch_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_patch_plan_count": len(records),
        "allowed_patch_plan_count": len(allowed),
        "latest_patch_plan_id": latest.patch_plan_id if latest else None,
        "latest_patch_plan_status": latest.patch_plan_status if latest else None,
        "latest_patch_plan_decision": latest.patch_plan_decision if latest else None,
        "latest_patch_plan_allowed": latest.patch_plan_allowed if latest else None,
        "latest_target_branch_type": latest.target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_patch_plan_hash": latest.patch_plan_hash if latest else None,
    }


def _latest_review(profile: Path) -> CortexMaterializationReviewGateRecord | None:
    records = CortexMaterializationReviewGateJsonlStore(profile / CORTEX_MATERIALIZATION_REVIEW_GATE_FILENAME).load()
    return records[-1] if records else None


def _matching_materialization(
    profile: Path,
    review: CortexMaterializationReviewGateRecord | None,
) -> CortexMaterializationPlanRecord | None:
    if review is None or not review.source_materialization_hash:
        return None
    records = CortexMaterializationPlanJsonlStore(profile / CORTEX_MATERIALIZATION_PLAN_FILENAME).load()
    for record in reversed(records):
        if record.materialization_hash == review.source_materialization_hash:
            return record
    return None


def _patch_plan_record(
    profile: Path,
    review: CortexMaterializationReviewGateRecord | None,
    materialization: CortexMaterializationPlanRecord | None,
) -> CortexLocalPatchPlanRecord:
    blockers = _patch_plan_blockers(review, materialization)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "local_patch_plan_ready" if allowed else "local_patch_plan_blocked"
    next_action = "await_local_patch_plan_review" if allowed else "repair_materialization_review_gate"
    reasons = ["materialization_review_ready", "local_patch_plan_prepared"] if allowed else blockers
    patch_units = _patch_units(materialization) if allowed and materialization else []
    verification_commands = _verification_commands(materialization) if allowed and materialization else []
    safety_constraints = list(materialization.safety_constraints) if allowed and materialization else []
    stop_conditions = list(materialization.stop_conditions) if allowed and materialization else []
    patch_plan_hash = _hash(
        str(profile),
        review.review_hash if review else "missing_review",
        materialization.materialization_hash if materialization else "missing_materialization",
        decision,
        next_action,
        *[unit.unit_id for unit in patch_units],
        *verification_commands,
        *reasons,
    )
    return CortexLocalPatchPlanRecord(
        profile_path=str(profile),
        source_materialization_review_id=review.review_id if review else None,
        source_materialization_review_hash=review.review_hash if review else None,
        source_materialization_hash=materialization.materialization_hash if materialization else None,
        source_ack_hash=materialization.source_ack_hash if materialization else None,
        source_packet_hash=materialization.source_packet_hash if materialization else None,
        source_plan_hash=materialization.source_plan_hash if materialization else None,
        target_branch_type=materialization.target_branch_type if materialization else None,
        patch_scope="local_plan_only",
        patch_units=patch_units,
        verification_commands=verification_commands,
        safety_constraints=safety_constraints,
        stop_conditions=stop_conditions,
        patch_plan_status=status,
        patch_plan_decision=decision,
        patch_plan_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        patch_plan_hash=patch_plan_hash,
        reasons=reasons,
    )


def _patch_units(materialization: CortexMaterializationPlanRecord) -> list[CortexLocalPatchUnit]:
    units = []
    for index, file_path in enumerate(materialization.allowed_files, start=1):
        operation = f"prepare:{file_path}"
        units.append(
            CortexLocalPatchUnit(
                unit_id=f"patch_unit_{index:03d}",
                file_path=file_path,
                operation="prepare_local_patch_unit",
                source_operation=operation,
                expected_review="local_patch_plan_review",
            )
        )
    return units


def _verification_commands(materialization: CortexMaterializationPlanRecord) -> list[str]:
    return ["python -m pytest"] + [f"verify:{test_name}" for test_name in materialization.required_tests]


def _patch_plan_blockers(
    review: CortexMaterializationReviewGateRecord | None,
    materialization: CortexMaterializationPlanRecord | None,
) -> list[str]:
    blockers = []
    if review is None:
        return ["missing_materialization_review_gate"]
    if review.review_allowed is not True:
        blockers.append("materialization_review_not_allowed")
    if review.review_decision != "materialization_review_ready":
        blockers.append("materialization_review_not_ready")
    if review.next_action != "emit_local_patch_plan":
        blockers.append("review_not_waiting_local_patch_plan")
    if materialization is None:
        blockers.append("missing_source_materialization_plan")
    elif review.source_materialization_hash != materialization.materialization_hash:
        blockers.append("source_materialization_hash_mismatch")
    if materialization is not None and not materialization.allowed_files:
        blockers.append("missing_allowed_files")
    if materialization is not None and not materialization.required_tests:
        blockers.append("missing_required_tests")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
