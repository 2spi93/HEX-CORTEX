from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_branch_plan_review_gate import (
    CORTEX_BRANCH_PLAN_REVIEW_GATE_FILENAME,
    CortexBranchPlanReviewGateJsonlStore,
    CortexBranchPlanReviewGateRecord,
)
from hex_cortex.memory.cortex_frontier_branch_plan import (
    CORTEX_FRONTIER_BRANCH_PLAN_FILENAME,
    CortexFrontierBranchPlanJsonlStore,
    CortexFrontierBranchPlanRecord,
)

CORTEX_BRANCH_BUILD_PACKET_FILENAME = "cortex-branch-build-packet.jsonl"


class CortexBranchBuildPacketRecord(BaseModel):
    packet_id: str = Field(default_factory=lambda: f"cortex_branch_build_packet_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_review_id: str | None
    source_review_hash: str | None
    source_plan_id: str | None
    source_plan_hash: str | None
    source_evaluator_hash: str | None
    source_tree_hash: str | None
    target_branch_type: str | None
    best_node_id: str | None
    authorized_files: list[str]
    required_tests: list[str]
    branch_steps: list[str]
    risk_controls: list[str]
    cost_controls: list[str]
    stop_conditions: list[str]
    packet_status: str
    packet_decision: str
    packet_allowed: bool
    next_action: str
    blockers: list[str]
    packet_hash: str
    reasons: list[str]


class CortexBranchBuildPacketJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexBranchBuildPacketRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexBranchBuildPacketRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex branch build packet {line_number}") from exc
        return records

    def save(self, records: list[CortexBranchBuildPacketRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_branch_build_packet(profile: Path) -> dict[str, object]:
    review = _latest_review(profile)
    plan = _matching_plan(profile, review)
    record = _packet_record(profile, review, plan)
    path = profile / CORTEX_BRANCH_BUILD_PACKET_FILENAME
    store = CortexBranchBuildPacketJsonlStore(path)
    current = store.load()
    if record.source_review_hash and any(item.source_review_hash == record.source_review_hash for item in current):
        records: list[CortexBranchBuildPacketRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "packet_type": "cortex_branch_build_packet",
        "profile_path": str(profile),
        "packet_path": str(path),
        "packet_count": count,
        "packet_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_branch_build_packets(path: Path) -> dict[str, object]:
    records = CortexBranchBuildPacketJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.packet_allowed]
    return {
        "inspect_type": "cortex_branch_build_packet",
        "path": str(path),
        "exists": path.exists(),
        "total_packet_count": len(records),
        "allowed_packet_count": len(allowed),
        "latest_packet_id": latest.packet_id if latest else None,
        "latest_packet_status": latest.packet_status if latest else None,
        "latest_packet_decision": latest.packet_decision if latest else None,
        "latest_packet_allowed": latest.packet_allowed if latest else None,
        "latest_target_branch_type": latest.target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_packet_hash": latest.packet_hash if latest else None,
    }


def _latest_review(profile: Path) -> CortexBranchPlanReviewGateRecord | None:
    records = CortexBranchPlanReviewGateJsonlStore(profile / CORTEX_BRANCH_PLAN_REVIEW_GATE_FILENAME).load()
    return records[-1] if records else None


def _matching_plan(
    profile: Path,
    review: CortexBranchPlanReviewGateRecord | None,
) -> CortexFrontierBranchPlanRecord | None:
    if review is None or not review.source_plan_hash:
        return None
    records = CortexFrontierBranchPlanJsonlStore(profile / CORTEX_FRONTIER_BRANCH_PLAN_FILENAME).load()
    for record in reversed(records):
        if record.plan_hash == review.source_plan_hash:
            return record
    return None


def _packet_record(
    profile: Path,
    review: CortexBranchPlanReviewGateRecord | None,
    plan: CortexFrontierBranchPlanRecord | None,
) -> CortexBranchBuildPacketRecord:
    blockers = _packet_blockers(review, plan)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "branch_build_packet_ready" if allowed else "branch_build_packet_blocked"
    next_action = "await_operator_build_go" if allowed else "repair_branch_plan_review_gate"
    reasons = ["review_gate_ready", "build_packet_prepared"] if allowed else blockers
    authorized_files = list(plan.planned_files) if allowed and plan else []
    required_tests = list(plan.planned_tests) if allowed and plan else []
    branch_steps = [step.step_id for step in plan.branch_steps] if allowed and plan else []
    risk_controls = list(plan.risk_controls) if allowed and plan else []
    cost_controls = list(plan.cost_controls) if allowed and plan else []
    stop_conditions = list(plan.stop_conditions) if allowed and plan else []
    packet_hash = _hash(
        str(profile),
        review.review_hash if review else "missing_review",
        plan.plan_hash if plan else "missing_plan",
        decision,
        next_action,
        *authorized_files,
        *required_tests,
        *reasons,
    )
    return CortexBranchBuildPacketRecord(
        profile_path=str(profile),
        source_review_id=review.review_id if review else None,
        source_review_hash=review.review_hash if review else None,
        source_plan_id=plan.plan_id if plan else None,
        source_plan_hash=plan.plan_hash if plan else None,
        source_evaluator_hash=plan.source_evaluator_hash if plan else None,
        source_tree_hash=plan.source_tree_hash if plan else None,
        target_branch_type=plan.target_branch_type if plan else None,
        best_node_id=plan.best_node_id if plan else None,
        authorized_files=authorized_files,
        required_tests=required_tests,
        branch_steps=branch_steps,
        risk_controls=risk_controls,
        cost_controls=cost_controls,
        stop_conditions=stop_conditions,
        packet_status=status,
        packet_decision=decision,
        packet_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        packet_hash=packet_hash,
        reasons=reasons,
    )


def _packet_blockers(
    review: CortexBranchPlanReviewGateRecord | None,
    plan: CortexFrontierBranchPlanRecord | None,
) -> list[str]:
    blockers = []
    if review is None:
        return ["missing_branch_plan_review_gate"]
    if review.review_allowed is not True:
        blockers.append("branch_plan_review_gate_not_allowed")
    if review.review_decision != "branch_plan_review_ready":
        blockers.append("branch_plan_review_gate_not_ready")
    if review.next_action != "prepare_branch_build_packet":
        blockers.append("review_gate_not_waiting_build_packet")
    if plan is None:
        blockers.append("missing_source_frontier_branch_plan")
    elif review.source_plan_hash != plan.plan_hash:
        blockers.append("source_plan_hash_mismatch")
    if plan is not None and (not plan.planned_files or not plan.planned_tests):
        blockers.append("missing_files_or_tests")
    if plan is not None and not plan.stop_conditions:
        blockers.append("missing_stop_conditions")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
