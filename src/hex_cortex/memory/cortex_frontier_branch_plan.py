from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_hypothesis_frontier_evaluator import (
    CORTEX_HYPOTHESIS_FRONTIER_EVALUATOR_FILENAME,
    CortexHypothesisFrontierEvaluation,
    CortexHypothesisFrontierEvaluatorJsonlStore,
    CortexHypothesisFrontierEvaluatorRecord,
)

CORTEX_FRONTIER_BRANCH_PLAN_FILENAME = "cortex-frontier-branch-plan.jsonl"


class CortexFrontierBranchPlanStep(BaseModel):
    step_id: str
    title: str
    description: str
    expected_output: str
    stop_condition: str


class CortexFrontierBranchPlanRecord(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"cortex_frontier_branch_plan_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_evaluator_id: str | None
    source_evaluator_hash: str | None
    source_tree_hash: str | None
    best_node_id: str | None
    best_total_score: float | None = Field(default=None, ge=0.0, le=1.0)
    branch_goal: str
    target_branch_type: str
    planned_files: list[str]
    planned_tests: list[str]
    branch_steps: list[CortexFrontierBranchPlanStep]
    risk_controls: list[str]
    cost_controls: list[str]
    stop_conditions: list[str]
    plan_status: str
    plan_decision: str
    plan_allowed: bool
    next_action: str
    blockers: list[str]
    plan_hash: str
    reasons: list[str]


class CortexFrontierBranchPlanJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexFrontierBranchPlanRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexFrontierBranchPlanRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex frontier branch plan {line_number}") from exc
        return records

    def save(self, records: list[CortexFrontierBranchPlanRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_frontier_branch_plan(profile: Path) -> dict[str, object]:
    evaluator = _latest_evaluator(profile)
    record = _plan_record(profile, evaluator)
    path = profile / CORTEX_FRONTIER_BRANCH_PLAN_FILENAME
    store = CortexFrontierBranchPlanJsonlStore(path)
    current = store.load()
    if record.source_evaluator_hash and any(item.source_evaluator_hash == record.source_evaluator_hash for item in current):
        records: list[CortexFrontierBranchPlanRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "plan_type": "cortex_frontier_branch_plan",
        "profile_path": str(profile),
        "plan_path": str(path),
        "plan_count": count,
        "plan_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_frontier_branch_plans(path: Path) -> dict[str, object]:
    records = CortexFrontierBranchPlanJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.plan_allowed]
    return {
        "inspect_type": "cortex_frontier_branch_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_plan_count": len(records),
        "allowed_plan_count": len(allowed),
        "latest_plan_id": latest.plan_id if latest else None,
        "latest_plan_status": latest.plan_status if latest else None,
        "latest_plan_decision": latest.plan_decision if latest else None,
        "latest_plan_allowed": latest.plan_allowed if latest else None,
        "latest_best_node_id": latest.best_node_id if latest else None,
        "latest_target_branch_type": latest.target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_plan_hash": latest.plan_hash if latest else None,
    }


def _latest_evaluator(profile: Path) -> CortexHypothesisFrontierEvaluatorRecord | None:
    records = CortexHypothesisFrontierEvaluatorJsonlStore(
        profile / CORTEX_HYPOTHESIS_FRONTIER_EVALUATOR_FILENAME
    ).load()
    return records[-1] if records else None


def _plan_record(
    profile: Path,
    evaluator: CortexHypothesisFrontierEvaluatorRecord | None,
) -> CortexFrontierBranchPlanRecord:
    blockers = _plan_blockers(evaluator)
    best = _best_evaluation(evaluator) if not blockers and evaluator else None
    allowed = not blockers and best is not None
    status = "ready" if allowed else "blocked"
    decision = "frontier_branch_plan_ready" if allowed else "frontier_branch_plan_blocked"
    next_action = "await_branch_plan_review" if allowed else "repair_hypothesis_frontier_evaluator"
    steps = _steps(best) if allowed and best else []
    planned_files = _planned_files(best) if allowed and best else []
    planned_tests = _planned_tests(best) if allowed and best else []
    risk_controls = _risk_controls() if allowed else []
    cost_controls = _cost_controls() if allowed else []
    stop_conditions = _stop_conditions() if allowed else []
    reasons = ["best_frontier_selected", "branch_plan_prepared"] if allowed else blockers
    plan_hash = _hash(
        str(profile),
        evaluator.evaluator_hash if evaluator else "missing_evaluator",
        best.node_id if best else "missing_best",
        decision,
        next_action,
        *planned_files,
        *planned_tests,
        *reasons,
    )
    return CortexFrontierBranchPlanRecord(
        profile_path=str(profile),
        source_evaluator_id=evaluator.evaluator_id if evaluator else None,
        source_evaluator_hash=evaluator.evaluator_hash if evaluator else None,
        source_tree_hash=evaluator.source_tree_hash if evaluator else None,
        best_node_id=best.node_id if best else None,
        best_total_score=best.total_score if best else None,
        branch_goal=_branch_goal(best) if best else "Repair evaluator before planning.",
        target_branch_type=_target_branch_type(best) if best else "repair",
        planned_files=planned_files,
        planned_tests=planned_tests,
        branch_steps=steps,
        risk_controls=risk_controls,
        cost_controls=cost_controls,
        stop_conditions=stop_conditions,
        plan_status=status,
        plan_decision=decision,
        plan_allowed=allowed,
        next_action=next_action,
        blockers=blockers if blockers else ([] if best else ["missing_best_frontier_evaluation"]),
        plan_hash=plan_hash,
        reasons=reasons,
    )


def _best_evaluation(
    evaluator: CortexHypothesisFrontierEvaluatorRecord,
) -> CortexHypothesisFrontierEvaluation | None:
    if evaluator.best_node_id:
        for item in evaluator.evaluations:
            if item.node_id == evaluator.best_node_id:
                return item
    return max(evaluator.evaluations, key=lambda item: item.total_score) if evaluator.evaluations else None


def _branch_goal(best: CortexHypothesisFrontierEvaluation) -> str:
    return f"Turn {best.node_id} into the next minimal, testable branch plan."


def _target_branch_type(best: CortexHypothesisFrontierEvaluation) -> str:
    if "state:build_choice" in best.node_id:
        return "memory_first_build_branch"
    if "rule:active_frame" in best.node_id:
        return "rule_consolidation_branch"
    if "learning:" in best.node_id:
        return "learning_reinforcement_branch"
    return "frontier_branch"


def _planned_files(best: CortexHypothesisFrontierEvaluation) -> list[str]:
    branch_type = _target_branch_type(best)
    if branch_type == "memory_first_build_branch":
        return [
            "src/hex_cortex/memory/cortex_frontier_branch_plan.py",
            "src/hex_cortex/memory/cortex_frontier_branch_plan_cli.py",
            "tests/test_cortex_frontier_branch_plan.py",
        ]
    return [
        "src/hex_cortex/memory/cortex_frontier_branch_plan.py",
        "tests/test_cortex_frontier_branch_plan.py",
    ]


def _planned_tests(best: CortexHypothesisFrontierEvaluation) -> list[str]:
    return [
        "plan builds from ready evaluator",
        "plan blocks from invalid evaluator",
        "plan is idempotent by evaluator hash",
        "summary reads latest plan",
    ]


def _steps(best: CortexHypothesisFrontierEvaluation) -> list[CortexFrontierBranchPlanStep]:
    return [
        CortexFrontierBranchPlanStep(
            step_id="select_frontier",
            title="Select frontier branch",
            description=f"Use best node {best.node_id} with score {best.total_score}.",
            expected_output="best frontier branch identified",
            stop_condition="best_node_id is missing",
        ),
        CortexFrontierBranchPlanStep(
            step_id="bound_scope",
            title="Bound implementation scope",
            description="Limit the branch to append-only plan artifacts and tests.",
            expected_output="bounded file and test list",
            stop_condition="plan expands beyond listed files",
        ),
        CortexFrontierBranchPlanStep(
            step_id="prepare_review",
            title="Prepare review gate",
            description="Leave actual mutation to a later reviewed step.",
            expected_output="branch plan ready for review",
            stop_condition="review gate is skipped",
        ),
    ]


def _risk_controls() -> list[str]:
    return [
        "no direct runtime mutation from the plan",
        "keep branch scope small",
        "preserve source evaluator and tree hashes",
    ]


def _cost_controls() -> list[str]:
    return [
        "prefer existing JSONL conventions",
        "avoid loading unrelated memory",
        "add only targeted tests",
    ]


def _stop_conditions() -> list[str]:
    return [
        "pytest fails",
        "source evaluator is missing or blocked",
        "best frontier node is missing",
        "plan attempts to bypass review",
    ]


def _plan_blockers(evaluator: CortexHypothesisFrontierEvaluatorRecord | None) -> list[str]:
    if evaluator is None:
        return ["missing_hypothesis_frontier_evaluator"]
    if evaluator.evaluator_allowed is not True:
        return ["hypothesis_frontier_evaluator_not_allowed"]
    if evaluator.evaluator_decision != "hypothesis_frontier_evaluator_ready":
        return ["hypothesis_frontier_evaluator_not_ready"]
    if evaluator.next_action != "prepare_frontier_branch_plan":
        return ["evaluator_not_waiting_frontier_branch_plan"]
    if not evaluator.best_node_id:
        return ["missing_best_node_id"]
    if evaluator.best_total_score is None or evaluator.best_total_score < 0.70:
        return ["best_frontier_score_too_low"]
    return []


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
