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

CORTEX_MATERIALIZATION_REVIEW_GATE_FILENAME = "cortex-materialization-review-gate.jsonl"


class CortexMaterializationReviewGateRecord(BaseModel):
    review_id: str = Field(default_factory=lambda: f"cortex_materialization_review_gate_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_materialization_id: str | None
    source_materialization_hash: str | None
    source_ack_hash: str | None
    source_packet_hash: str | None
    source_review_hash: str | None
    source_plan_hash: str | None
    target_branch_type: str | None
    reviewed_file_count: int = Field(ge=0)
    reviewed_operation_count: int = Field(ge=0)
    reviewed_test_count: int = Field(ge=0)
    reviewed_stop_condition_count: int = Field(ge=0)
    scope_verdict: str
    operation_verdict: str
    safety_verdict: str
    lineage_verdict: str
    review_status: str
    review_decision: str
    review_allowed: bool
    next_action: str
    blockers: list[str]
    review_hash: str
    reasons: list[str]


class CortexMaterializationReviewGateJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexMaterializationReviewGateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexMaterializationReviewGateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex materialization review gate {line_number}") from exc
        return records

    def save(self, records: list[CortexMaterializationReviewGateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_materialization_review_gate(profile: Path) -> dict[str, object]:
    materialization = _latest_materialization(profile)
    record = _review_record(profile, materialization)
    path = profile / CORTEX_MATERIALIZATION_REVIEW_GATE_FILENAME
    store = CortexMaterializationReviewGateJsonlStore(path)
    current = store.load()
    if record.source_materialization_hash and any(
        item.source_materialization_hash == record.source_materialization_hash for item in current
    ):
        records: list[CortexMaterializationReviewGateRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "review_type": "cortex_materialization_review_gate",
        "profile_path": str(profile),
        "review_path": str(path),
        "review_count": count,
        "review_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_materialization_review_gates(path: Path) -> dict[str, object]:
    records = CortexMaterializationReviewGateJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.review_allowed]
    return {
        "inspect_type": "cortex_materialization_review_gate",
        "path": str(path),
        "exists": path.exists(),
        "total_review_count": len(records),
        "allowed_review_count": len(allowed),
        "latest_review_id": latest.review_id if latest else None,
        "latest_review_status": latest.review_status if latest else None,
        "latest_review_decision": latest.review_decision if latest else None,
        "latest_review_allowed": latest.review_allowed if latest else None,
        "latest_target_branch_type": latest.target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_review_hash": latest.review_hash if latest else None,
    }


def _latest_materialization(profile: Path) -> CortexMaterializationPlanRecord | None:
    records = CortexMaterializationPlanJsonlStore(profile / CORTEX_MATERIALIZATION_PLAN_FILENAME).load()
    return records[-1] if records else None


def _review_record(
    profile: Path,
    materialization: CortexMaterializationPlanRecord | None,
) -> CortexMaterializationReviewGateRecord:
    blockers = _review_blockers(materialization)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "materialization_review_ready" if allowed else "materialization_review_blocked"
    next_action = "emit_local_patch_plan" if allowed else "repair_materialization_plan"
    reasons = ["materialization_scope_reviewed", "materialization_review_gate_ready"] if allowed else blockers
    review_hash = _hash(
        str(profile),
        materialization.materialization_hash if materialization else "missing_materialization",
        decision,
        next_action,
        *reasons,
    )
    return CortexMaterializationReviewGateRecord(
        profile_path=str(profile),
        source_materialization_id=materialization.materialization_id if materialization else None,
        source_materialization_hash=materialization.materialization_hash if materialization else None,
        source_ack_hash=materialization.source_ack_hash if materialization else None,
        source_packet_hash=materialization.source_packet_hash if materialization else None,
        source_review_hash=materialization.source_review_hash if materialization else None,
        source_plan_hash=materialization.source_plan_hash if materialization else None,
        target_branch_type=materialization.target_branch_type if materialization else None,
        reviewed_file_count=len(materialization.allowed_files) if materialization else 0,
        reviewed_operation_count=len(materialization.planned_operations) if materialization else 0,
        reviewed_test_count=len(materialization.required_tests) if materialization else 0,
        reviewed_stop_condition_count=len(materialization.stop_conditions) if materialization else 0,
        scope_verdict=_scope_verdict(materialization),
        operation_verdict=_operation_verdict(materialization),
        safety_verdict=_safety_verdict(materialization),
        lineage_verdict=_lineage_verdict(materialization),
        review_status=status,
        review_decision=decision,
        review_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        review_hash=review_hash,
        reasons=reasons,
    )


def _review_blockers(materialization: CortexMaterializationPlanRecord | None) -> list[str]:
    blockers = []
    if materialization is None:
        return ["missing_materialization_plan"]
    if materialization.materialization_allowed is not True:
        blockers.append("materialization_plan_not_allowed")
    if materialization.materialization_decision != "materialization_plan_ready":
        blockers.append("materialization_plan_not_ready")
    if materialization.next_action != "await_materialization_review":
        blockers.append("materialization_not_waiting_review_gate")
    if materialization.materialization_scope != "declarative_only":
        blockers.append("materialization_scope_not_declarative")
    if not materialization.allowed_files:
        blockers.append("missing_allowed_files")
    if not materialization.required_tests:
        blockers.append("missing_required_tests")
    if not materialization.safety_constraints:
        blockers.append("missing_safety_constraints")
    if not materialization.stop_conditions:
        blockers.append("missing_stop_conditions")
    if set(materialization.planned_operations) != {f"prepare:{path}" for path in materialization.allowed_files}:
        blockers.append("planned_operations_do_not_match_allowed_files")
    if not all(
        [
            materialization.source_ack_hash,
            materialization.source_packet_hash,
            materialization.source_review_hash,
            materialization.source_plan_hash,
        ]
    ):
        blockers.append("missing_source_lineage")
    return blockers


def _scope_verdict(materialization: CortexMaterializationPlanRecord | None) -> str:
    if materialization is None:
        return "missing"
    return "declarative_scope" if materialization.materialization_scope == "declarative_only" else "scope_invalid"


def _operation_verdict(materialization: CortexMaterializationPlanRecord | None) -> str:
    if materialization is None:
        return "missing"
    expected = {f"prepare:{path}" for path in materialization.allowed_files}
    return "operations_match_files" if set(materialization.planned_operations) == expected else "operations_invalid"


def _safety_verdict(materialization: CortexMaterializationPlanRecord | None) -> str:
    if materialization is None:
        return "missing"
    return "safety_constraints_present" if materialization.safety_constraints and materialization.stop_conditions else "safety_incomplete"


def _lineage_verdict(materialization: CortexMaterializationPlanRecord | None) -> str:
    if materialization is None:
        return "missing"
    return "lineage_present" if all(
        [
            materialization.source_ack_hash,
            materialization.source_packet_hash,
            materialization.source_review_hash,
            materialization.source_plan_hash,
        ]
    ) else "lineage_missing"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
