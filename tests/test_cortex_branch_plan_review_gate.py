from hex_cortex.memory.cortex_branch_plan_review_gate import CORTEX_BRANCH_PLAN_REVIEW_GATE_FILENAME
from hex_cortex.memory.cortex_branch_plan_review_gate import CortexBranchPlanReviewGateRecord


def test_branch_plan_review_gate_imports() -> None:
    assert CORTEX_BRANCH_PLAN_REVIEW_GATE_FILENAME == "cortex-branch-plan-review-gate.jsonl"
    assert CortexBranchPlanReviewGateRecord.__name__ == "CortexBranchPlanReviewGateRecord"
