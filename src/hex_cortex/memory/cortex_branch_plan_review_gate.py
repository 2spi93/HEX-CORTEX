from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_frontier_branch_plan import (
    CORTEX_FRONTIER_BRANCH_PLAN_FILENAME,
    CortexFrontierBranchPlanJsonlStore,
    CortexFrontierBranchPlanRecord,
)

CORTEX_BRANCH_PLAN_REVIEW_GATE_FILENAME = "cortex-branch-plan-review-gate.jsonl"

_MAX_PLANNED_FILES = 4
_MIN_BRANCH_STEPS = 3
_MIN_PLANNED_TESTS = 2
_MIN_STOP_CONDITIONS = 3


class CortexBranchPlanReviewGateRecord(BaseModel):
    review_id: str = Field(default_factory=lambda: f"cortex_branch_plan_review_gate_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_plan_id: str | None
    source_plan_hash: str | None
    source_evaluator_hash: str | None
    source_tree_hash: str | None
    reviewed_best_node_id: str | None
    reviewed_target_branch_type: str | None
    reviewed_file_count: int = Field(ge=0)
    reviewed_test_count: int = Field(ge=0)
    reviewed_stop_condition_count: int = Field(ge=0)
    scope_verdict: str
    test_verdict: str
    stop_verdict: str
    lineage_verdict: str
    review_status: str
    review_decision: str
    review_allowed: bool
    next_action: str
    blockers: list[str]
    review_hash: str
    reasons: list[str]


class CortexBranchPlanReviewGateJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexBranchPlanReviewGateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexBranchPlanReviewGateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex branch plan review gate {line_number}") from exc
        return records

    def save(self, records: list[CortexBranchPlanReviewGateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_branch_plan_review_gate(profile: Path) -> dict[str, object]:
    plan = _latest_plan(profile)
    record = _review_record(profile, plan)
    path = profile / CORTEX_BRANCH_PLAN_REVIEW_GATE_FILENAME
    store = CortexBranchPlanReviewGateJsonlStore(path)
    current = store.load()
    if record.source_plan_hash and any(item.source_plan_hash == record.source_plan_hash for item in current):
        records: list[CortexBranchPlanReviewGateRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "review_type": "cortex_branch_plan_review_gate",
        "profile_path": str(profile),
        "review_path": str(path),
        "review_count": count,
        "review_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_branch_plan_review_gates(path: Path) -> dict[str, object]:
    records = CortexBranchPlanReviewGateJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.review_allowed]
    return {
        "inspect_type": "cortex_branch_plan_review_gate",
        "path": str(path),
        "exists": path.exists(),
        "total_review_count": len(records),
        "allowed_review_count": len(allowed),
        "latest_review_id": latest.review_id if latest else None,
        "latest_review_status": latest.review_status if latest else None,
        "latest_review_decision": latest.review_decision if latest else None,
        "latest_review_allowed": latest.review_allowed if latest else None,
        "latest_reviewed_target_branch_type": latest.reviewed_target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_review_hash": latest.review_hash if latest else None,
    }


def _latest_plan(profile: Path) -> CortexFrontierBranchPlanRecord | None:
    records = CortexFrontierBranchPlanJsonlStore(profile / CORTEX_FRONTIER_BRANCH_PLAN_FILENAME).load()
    return records[-1] if records else None


def _review_record(
    profile: Path,
    plan: CortexFrontierBranchPlanRecord | None,
) -> CortexBranchPlanReviewGateRecord:
    blockers = _review_blockers(plan)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "branch_plan_review_ready" if allowed else "branch_plan_review_blocked"
    next_action = "prepare_branch_build_packet" if allowed else "repair_frontier_branch_plan"
    reasons = ["plan_scope_reviewed", "plan_review_gate_ready"] if allowed else blockers
    review_hash = _hash(
        str(profile),
        plan.plan_hash if plan else "missing_plan",
        decision,
        next_action,
        *reasons,
    )
    return CortexBranchPlanReviewGateRecord(
        profile_path=str(profile),
        source_plan_id=plan.plan_id if plan else None,
        source_plan_hash=plan.plan_hash if plan else None,
        source_evaluator_hash=plan.source_evaluator_hash if plan else None,
        source_tree_hash=plan.source_tree_hash if plan else None,
        reviewed_best_node_id=plan.best_node_id if plan else None,
        reviewed_target_branch_type=plan.target_branch_type if plan else None,
        reviewed_file_count=len(plan.planned_files) if plan else 0,
        reviewed_test_count=len(plan.planned_tests) if plan else 0,
        reviewed_stop_condition_count=len(plan.stop_conditions) if plan else 0,
        scope_verdict=_scope_verdict(plan),
        test_verdict=_test_verdict(plan),
        stop_verdict=_stop_verdict(plan),
        lineage_verdict=_lineage_verdict(plan),
        review_status=status,
        review_decision=decision,
        review_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        review_hash=review_hash,
        reasons=reasons,
    )


def _review_blockers(plan: CortexFrontierBranchPlanRecord | None) -> list[str]:
    blockers = []
    if plan is None:
        return ["missing_frontier_branch_plan"]
    if plan.plan_allowed is not True:
        blockers.append("frontier_branch_plan_not_allowed")
    if plan.plan_decision != "frontier_branch_plan_ready":
        blockers.append("frontier_branch_plan_not_ready")
    if plan.next_action != "await_branch_plan_review":
        blockers.append("plan_not_waiting_review_gate")
    if not plan.best_node_id:
        blockers.append("missing_best_node_id")
    if plan.target_branch_type == "repair":
        blockers.append("target_branch_type_repair")
    if len(plan.planned_files) == 0 or len(plan.planned_files) > _MAX_PLANNED_FILES:
        blockers.append("planned_file_scope_invalid")
    if len(plan.planned_tests) < _MIN_PLANNED_TESTS:
        blockers.append("planned_tests_insufficient")
    if len(plan.branch_steps) < _MIN_BRANCH_STEPS:
        blockers.append("branch_steps_insufficient")
    if len(plan.stop_conditions) < _MIN_STOP_CONDITIONS:
        blockers.append("stop_conditions_insufficient")
    if not plan.risk_controls or not plan.cost_controls:
        blockers.append("missing_risk_or_cost_controls")
    if not plan.source_evaluator_hash or not plan.source_tree_hash:
        blockers.append("missing_source_lineage")
    return blockers


def _scope_verdict(plan: CortexFrontierBranchPlanRecord | None) -> str:
    if plan is None:
        return "missing"
    return "small_scope" if 0 < len(plan.planned_files) <= _MAX_PLANNED_FILES else "scope_invalid"


def _test_verdict(plan: CortexFrontierBranchPlanRecord | None) -> str:
    if plan is None:
        return "missing"
    return "tests_planned" if len(plan.planned_tests) >= _MIN_PLANNED_TESTS else "tests_insufficient"


def _stop_verdict(plan: CortexFrontierBranchPlanRecord | None) -> str:
    if plan is None:
        return "missing"
    return "stop_conditions_present" if len(plan.stop_conditions) >= _MIN_STOP_CONDITIONS else "stop_conditions_insufficient"


def _lineage_verdict(plan: CortexFrontierBranchPlanRecord | None) -> str:
    if plan is None:
        return "missing"
    return "lineage_present" if plan.source_evaluator_hash and plan.source_tree_hash else "lineage_missing"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
