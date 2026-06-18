from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_hypothesis_tree import (
    CORTEX_HYPOTHESIS_TREE_FILENAME,
    CortexHypothesisNode,
    CortexHypothesisTreeJsonlStore,
    CortexHypothesisTreeRecord,
)

CORTEX_HYPOTHESIS_FRONTIER_EVALUATOR_FILENAME = "cortex-hypothesis-frontier-evaluator.jsonl"


class CortexHypothesisFrontierEvaluation(BaseModel):
    node_id: str
    hypothesis: str
    evidence_score: float = Field(ge=0.0, le=1.0)
    future_score: float = Field(ge=0.0, le=1.0)
    cost_score: float = Field(ge=0.0, le=1.0)
    total_score: float = Field(ge=0.0, le=1.0)
    verdict: str
    source_block_ids: list[str]
    latent_state: str
    predicted_future: str
    cost_estimate: str


class CortexHypothesisFrontierEvaluatorRecord(BaseModel):
    evaluator_id: str = Field(default_factory=lambda: f"cortex_hypothesis_frontier_evaluator_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_tree_id: str | None
    source_tree_hash: str | None
    evaluator_status: str
    evaluator_decision: str
    evaluator_allowed: bool
    frontier_count: int = Field(ge=0)
    evaluations: list[CortexHypothesisFrontierEvaluation]
    best_node_id: str | None
    best_total_score: float | None = Field(default=None, ge=0.0, le=1.0)
    next_action: str
    blockers: list[str]
    evaluator_hash: str
    reasons: list[str]


class CortexHypothesisFrontierEvaluatorJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexHypothesisFrontierEvaluatorRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexHypothesisFrontierEvaluatorRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex hypothesis frontier evaluator {line_number}") from exc
        return records

    def save(self, records: list[CortexHypothesisFrontierEvaluatorRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_hypothesis_frontier_evaluator(profile: Path) -> dict[str, object]:
    tree = _latest_tree(profile)
    record = _evaluator_record(profile, tree)
    path = profile / CORTEX_HYPOTHESIS_FRONTIER_EVALUATOR_FILENAME
    store = CortexHypothesisFrontierEvaluatorJsonlStore(path)
    current = store.load()
    if record.source_tree_hash and any(item.source_tree_hash == record.source_tree_hash for item in current):
        records: list[CortexHypothesisFrontierEvaluatorRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "evaluator_type": "cortex_hypothesis_frontier_evaluator",
        "profile_path": str(profile),
        "evaluator_path": str(path),
        "evaluator_count": count,
        "evaluator_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_hypothesis_frontier_evaluators(path: Path) -> dict[str, object]:
    records = CortexHypothesisFrontierEvaluatorJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.evaluator_allowed]
    return {
        "inspect_type": "cortex_hypothesis_frontier_evaluator",
        "path": str(path),
        "exists": path.exists(),
        "total_evaluator_count": len(records),
        "allowed_evaluator_count": len(allowed),
        "latest_evaluator_id": latest.evaluator_id if latest else None,
        "latest_evaluator_status": latest.evaluator_status if latest else None,
        "latest_evaluator_decision": latest.evaluator_decision if latest else None,
        "latest_evaluator_allowed": latest.evaluator_allowed if latest else None,
        "latest_frontier_count": latest.frontier_count if latest else None,
        "latest_best_node_id": latest.best_node_id if latest else None,
        "latest_best_total_score": latest.best_total_score if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_evaluator_hash": latest.evaluator_hash if latest else None,
    }


def _latest_tree(profile: Path) -> CortexHypothesisTreeRecord | None:
    records = CortexHypothesisTreeJsonlStore(profile / CORTEX_HYPOTHESIS_TREE_FILENAME).load()
    return records[-1] if records else None


def _evaluator_record(
    profile: Path,
    tree: CortexHypothesisTreeRecord | None,
) -> CortexHypothesisFrontierEvaluatorRecord:
    blockers = _evaluator_blockers(tree)
    evaluations = [] if blockers or tree is None else [_evaluation(node) for node in _frontier_nodes(tree)]
    allowed = not blockers and bool(evaluations)
    best = max(evaluations, key=lambda item: item.total_score) if allowed else None
    status = "ready" if allowed else "blocked"
    decision = "hypothesis_frontier_evaluator_ready" if allowed else "hypothesis_frontier_evaluator_blocked"
    next_action = "prepare_frontier_branch_plan" if allowed else "repair_hypothesis_tree"
    reasons = ["frontier_scored", "best_branch_selected"] if allowed else blockers
    evaluator_hash = _hash(
        str(profile),
        tree.tree_hash if tree else "missing_tree",
        best.node_id if best else "missing_best",
        decision,
        next_action,
        *[item.node_id for item in evaluations],
        *reasons,
    )
    return CortexHypothesisFrontierEvaluatorRecord(
        profile_path=str(profile),
        source_tree_id=tree.tree_id if tree else None,
        source_tree_hash=tree.tree_hash if tree else None,
        evaluator_status=status,
        evaluator_decision=decision,
        evaluator_allowed=allowed,
        frontier_count=len(evaluations),
        evaluations=evaluations,
        best_node_id=best.node_id if best else None,
        best_total_score=best.total_score if best else None,
        next_action=next_action,
        blockers=blockers if blockers else ([] if evaluations else ["no_frontier_nodes_scored"]),
        evaluator_hash=evaluator_hash,
        reasons=reasons,
    )


def _frontier_nodes(tree: CortexHypothesisTreeRecord) -> list[CortexHypothesisNode]:
    return [node for node in tree.nodes if node.node_status == "frontier"]


def _evaluation(node: CortexHypothesisNode) -> CortexHypothesisFrontierEvaluation:
    evidence_score = node.score
    future_score = _future_score(node.predicted_future)
    cost_score = _cost_score(node.cost_estimate)
    total_score = round((0.45 * evidence_score) + (0.35 * future_score) + (0.20 * cost_score), 4)
    return CortexHypothesisFrontierEvaluation(
        node_id=node.node_id,
        hypothesis=node.hypothesis,
        evidence_score=round(evidence_score, 4),
        future_score=future_score,
        cost_score=cost_score,
        total_score=total_score,
        verdict="frontier_candidate_ready" if total_score >= 0.70 else "frontier_candidate_watch",
        source_block_ids=node.source_block_ids,
        latent_state=node.latent_state,
        predicted_future=node.predicted_future,
        cost_estimate=node.cost_estimate,
    )


def _future_score(predicted_future: str) -> float:
    text = predicted_future.lower()
    if "next memory" in text or "memory-first" in text:
        return 0.95
    if "trajectory" in text or "branch" in text:
        return 0.85
    if "drift" in text:
        return 0.75
    return 0.65


def _cost_score(cost_estimate: str) -> float:
    text = cost_estimate.lower()
    if "small" in text or "low" in text:
        return 0.95
    if "limits" in text or "reduces" in text:
        return 0.85
    if "prefer" in text:
        return 0.80
    return 0.65


def _evaluator_blockers(tree: CortexHypothesisTreeRecord | None) -> list[str]:
    if tree is None:
        return ["missing_hypothesis_tree"]
    if tree.tree_allowed is not True:
        return ["hypothesis_tree_not_allowed"]
    if tree.tree_decision != "hypothesis_tree_ready":
        return ["hypothesis_tree_not_ready"]
    if tree.next_action != "evaluate_hypothesis_frontier":
        return ["tree_not_waiting_frontier_evaluation"]
    if not tree.frontier_node_ids:
        return ["missing_frontier_nodes"]
    return []


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
