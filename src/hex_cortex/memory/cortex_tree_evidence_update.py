from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_hypothesis_tree import (
    CORTEX_HYPOTHESIS_TREE_FILENAME,
    CortexHypothesisTreeJsonlStore,
    CortexHypothesisTreeRecord,
)
from hex_cortex.memory.cortex_patch_test_receipt import (
    CORTEX_PATCH_TEST_RECEIPT_FILENAME,
    CortexPatchTestReceiptJsonlStore,
    CortexPatchTestReceiptRecord,
)

CORTEX_TREE_EVIDENCE_UPDATE_FILENAME = "cortex-tree-evidence-update.jsonl"


class CortexEvidenceUpdatedNode(BaseModel):
    node_id: str
    parent_id: str | None
    prior_score: float = Field(ge=0.0, le=1.0)
    evidence_delta: float = Field(ge=0.0, le=1.0)
    posterior_score: float = Field(ge=0.0, le=1.0)
    update_reason: str


class CortexTreeEvidenceUpdateRecord(BaseModel):
    update_id: str = Field(default_factory=lambda: f"cortex_tree_evidence_update_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_tree_id: str | None
    source_tree_hash: str | None
    source_receipt_id: str | None
    source_receipt_hash: str | None
    target_frontier_node_id: str | None
    updated_node_count: int = Field(ge=0)
    updated_nodes: list[CortexEvidenceUpdatedNode]
    test_status: str | None
    passed_count: int = Field(ge=0)
    evidence_score: float = Field(ge=0.0, le=1.0)
    cost_score: float = Field(ge=0.0, le=1.0)
    update_status: str
    update_decision: str
    update_allowed: bool
    next_action: str
    blockers: list[str]
    update_hash: str
    reasons: list[str]


class CortexTreeEvidenceUpdateJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexTreeEvidenceUpdateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexTreeEvidenceUpdateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex tree evidence update {line_number}") from exc
        return records

    def save(self, records: list[CortexTreeEvidenceUpdateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_tree_evidence_update(profile: Path) -> dict[str, object]:
    tree = _latest_tree(profile)
    receipt = _latest_receipt(profile)
    record = _update_record(profile, tree, receipt)
    path = profile / CORTEX_TREE_EVIDENCE_UPDATE_FILENAME
    store = CortexTreeEvidenceUpdateJsonlStore(path)
    current = store.load()
    if record.source_receipt_hash and any(item.source_receipt_hash == record.source_receipt_hash for item in current):
        records: list[CortexTreeEvidenceUpdateRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "update_type": "cortex_tree_evidence_update",
        "profile_path": str(profile),
        "update_path": str(path),
        "update_count": count,
        "update_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_tree_evidence_updates(path: Path) -> dict[str, object]:
    records = CortexTreeEvidenceUpdateJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.update_allowed]
    return {
        "inspect_type": "cortex_tree_evidence_update",
        "path": str(path),
        "exists": path.exists(),
        "total_update_count": len(records),
        "allowed_update_count": len(allowed),
        "latest_update_id": latest.update_id if latest else None,
        "latest_update_status": latest.update_status if latest else None,
        "latest_update_decision": latest.update_decision if latest else None,
        "latest_update_allowed": latest.update_allowed if latest else None,
        "latest_target_frontier_node_id": latest.target_frontier_node_id if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_update_hash": latest.update_hash if latest else None,
    }


def _latest_tree(profile: Path) -> CortexHypothesisTreeRecord | None:
    records = CortexHypothesisTreeJsonlStore(profile / CORTEX_HYPOTHESIS_TREE_FILENAME).load()
    return records[-1] if records else None


def _latest_receipt(profile: Path) -> CortexPatchTestReceiptRecord | None:
    records = CortexPatchTestReceiptJsonlStore(profile / CORTEX_PATCH_TEST_RECEIPT_FILENAME).load()
    return records[-1] if records else None


def _update_record(profile: Path, tree: CortexHypothesisTreeRecord | None, receipt: CortexPatchTestReceiptRecord | None) -> CortexTreeEvidenceUpdateRecord:
    blockers = _update_blockers(tree, receipt)
    allowed = not blockers
    target_node_id = _target_node_id(tree) if tree else None
    updated = _updated_nodes(tree, target_node_id, receipt) if allowed and tree and receipt else []
    status = "ready" if allowed else "blocked"
    decision = "tree_evidence_update_ready" if allowed else "tree_evidence_update_blocked"
    next_action = "create_outcome_learning_event" if allowed else "repair_tree_evidence_inputs"
    reasons = ["receipt_ready", "tree_path_updated"] if allowed else blockers
    evidence_score = _evidence_score(receipt) if receipt else 0.0
    cost_score = 1.0 if allowed else 0.0
    update_hash = _hash(
        str(profile),
        tree.tree_hash if tree else "missing_tree",
        receipt.receipt_hash if receipt else "missing_receipt",
        target_node_id or "missing_target",
        decision,
        next_action,
        *[node.node_id for node in updated],
        *reasons,
    )
    return CortexTreeEvidenceUpdateRecord(
        profile_path=str(profile),
        source_tree_id=tree.tree_id if tree else None,
        source_tree_hash=tree.tree_hash if tree else None,
        source_receipt_id=receipt.receipt_id if receipt else None,
        source_receipt_hash=receipt.receipt_hash if receipt else None,
        target_frontier_node_id=target_node_id,
        updated_node_count=len(updated),
        updated_nodes=updated,
        test_status=receipt.test_status if receipt else None,
        passed_count=receipt.passed_count if receipt else 0,
        evidence_score=evidence_score,
        cost_score=cost_score,
        update_status=status,
        update_decision=decision,
        update_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        update_hash=update_hash,
        reasons=reasons,
    )


def _target_node_id(tree: CortexHypothesisTreeRecord | None) -> str | None:
    if tree is None:
        return None
    preferred = "frontier:state:build_choice"
    if preferred in tree.frontier_node_ids:
        return preferred
    return tree.frontier_node_ids[0] if tree.frontier_node_ids else None


def _updated_nodes(tree: CortexHypothesisTreeRecord, target_node_id: str | None, receipt: CortexPatchTestReceiptRecord) -> list[CortexEvidenceUpdatedNode]:
    if not target_node_id:
        return []
    by_id = {node.node_id: node for node in tree.nodes}
    path = []
    current = by_id.get(target_node_id)
    while current is not None:
        path.append(current)
        current = by_id.get(current.parent_id) if current.parent_id else None
    path = list(reversed(path))
    delta = _evidence_score(receipt) * 0.05
    return [
        CortexEvidenceUpdatedNode(
            node_id=node.node_id,
            parent_id=node.parent_id,
            prior_score=node.score,
            evidence_delta=delta,
            posterior_score=min(1.0, node.score + delta),
            update_reason="receipt_passed",
        )
        for node in path
    ]


def _evidence_score(receipt: CortexPatchTestReceiptRecord) -> float:
    if receipt.receipt_allowed and receipt.test_status == "passed" and receipt.passed_count > 0:
        return 1.0
    return 0.0


def _update_blockers(tree: CortexHypothesisTreeRecord | None, receipt: CortexPatchTestReceiptRecord | None) -> list[str]:
    blockers = []
    if tree is None:
        return ["missing_hypothesis_tree"]
    if tree.tree_allowed is not True:
        blockers.append("hypothesis_tree_not_allowed")
    if not tree.frontier_node_ids:
        blockers.append("missing_frontier_nodes")
    if receipt is None:
        blockers.append("missing_patch_test_receipt")
    elif receipt.receipt_allowed is not True:
        blockers.append("patch_test_receipt_not_allowed")
    elif receipt.next_action != "backpropagate_hypothesis_tree":
        blockers.append("receipt_not_waiting_tree_update")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
