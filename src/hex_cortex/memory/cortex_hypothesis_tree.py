from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_memory_retrieval_selector import (
    CORTEX_MEMORY_RETRIEVAL_SELECTOR_FILENAME,
    CortexMemoryRetrievalSelectorJsonlStore,
    CortexMemoryRetrievalSelectorRecord,
)

CORTEX_HYPOTHESIS_TREE_FILENAME = "cortex-hypothesis-tree.jsonl"


class CortexHypothesisNode(BaseModel):
    node_id: str
    parent_id: str | None
    depth: int = Field(ge=0)
    hypothesis: str
    node_status: str
    score: float = Field(ge=0.0, le=1.0)
    source_block_ids: list[str]
    latent_state: str
    predicted_future: str
    cost_estimate: str


class CortexHypothesisTreeRecord(BaseModel):
    tree_id: str = Field(default_factory=lambda: f"cortex_hypothesis_tree_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_selector_id: str | None
    source_selector_hash: str | None
    tree_status: str
    tree_decision: str
    tree_allowed: bool
    root_node_id: str | None
    frontier_node_ids: list[str]
    node_count: int = Field(ge=0)
    nodes: list[CortexHypothesisNode]
    next_action: str
    blockers: list[str]
    tree_hash: str
    reasons: list[str]


class CortexHypothesisTreeJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexHypothesisTreeRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexHypothesisTreeRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex hypothesis tree {line_number}") from exc
        return records

    def save(self, records: list[CortexHypothesisTreeRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_hypothesis_tree(profile: Path) -> dict[str, object]:
    selector = _latest_selector(profile)
    record = _tree_record(profile, selector)
    path = profile / CORTEX_HYPOTHESIS_TREE_FILENAME
    store = CortexHypothesisTreeJsonlStore(path)
    current = store.load()
    if record.source_selector_hash and any(item.source_selector_hash == record.source_selector_hash for item in current):
        records: list[CortexHypothesisTreeRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "tree_type": "cortex_hypothesis_tree",
        "profile_path": str(profile),
        "tree_path": str(path),
        "tree_count": count,
        "tree_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_hypothesis_trees(path: Path) -> dict[str, object]:
    records = CortexHypothesisTreeJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.tree_allowed]
    return {
        "inspect_type": "cortex_hypothesis_tree",
        "path": str(path),
        "exists": path.exists(),
        "total_tree_count": len(records),
        "allowed_tree_count": len(allowed),
        "latest_tree_id": latest.tree_id if latest else None,
        "latest_tree_status": latest.tree_status if latest else None,
        "latest_tree_decision": latest.tree_decision if latest else None,
        "latest_tree_allowed": latest.tree_allowed if latest else None,
        "latest_node_count": latest.node_count if latest else None,
        "latest_frontier_node_ids": latest.frontier_node_ids if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_tree_hash": latest.tree_hash if latest else None,
    }


def _latest_selector(profile: Path) -> CortexMemoryRetrievalSelectorRecord | None:
    records = CortexMemoryRetrievalSelectorJsonlStore(
        profile / CORTEX_MEMORY_RETRIEVAL_SELECTOR_FILENAME
    ).load()
    return records[-1] if records else None


def _tree_record(profile: Path, selector: CortexMemoryRetrievalSelectorRecord | None) -> CortexHypothesisTreeRecord:
    blockers = _tree_blockers(selector)
    allowed = not blockers
    nodes = _nodes(selector) if allowed and selector else []
    status = "ready" if allowed else "blocked"
    decision = "hypothesis_tree_ready" if allowed else "hypothesis_tree_blocked"
    next_action = "evaluate_hypothesis_frontier" if allowed else "repair_memory_retrieval_selector"
    reasons = ["selector_ready", "hypothesis_frontier_seeded"] if allowed else blockers
    root_id = nodes[0].node_id if nodes else None
    frontier = [node.node_id for node in nodes if node.node_status == "frontier"]
    tree_hash = _hash(
        str(profile),
        selector.selector_hash if selector else "missing_selector",
        *[node.node_id for node in nodes],
        decision,
        next_action,
        *reasons,
    )
    return CortexHypothesisTreeRecord(
        profile_path=str(profile),
        source_selector_id=selector.selector_id if selector else None,
        source_selector_hash=selector.selector_hash if selector else None,
        tree_status=status,
        tree_decision=decision,
        tree_allowed=allowed,
        root_node_id=root_id,
        frontier_node_ids=frontier,
        node_count=len(nodes),
        nodes=nodes,
        next_action=next_action,
        blockers=blockers,
        tree_hash=tree_hash,
        reasons=reasons,
    )


def _nodes(selector: CortexMemoryRetrievalSelectorRecord) -> list[CortexHypothesisNode]:
    root = CortexHypothesisNode(
        node_id="root:memory_first",
        parent_id=None,
        depth=0,
        hypothesis="A small memory-first subsystem is the best next branch.",
        node_status="root",
        score=0.9,
        source_block_ids=selector.selected_block_ids,
        latent_state="memory-first build state",
        predicted_future="selector then evaluation before broader routing",
        cost_estimate="low",
    )
    children = [
        CortexHypothesisNode(
            node_id=f"frontier:{block.block_id}",
            parent_id=root.node_id,
            depth=1,
            hypothesis=f"Use block {block.block_id} as evidence for the next memory branch.",
            node_status="frontier",
            score=min(1.0, block.priority / 100),
            source_block_ids=[block.block_id],
            latent_state=block.latent_role,
            predicted_future=block.future_role,
            cost_estimate=block.cost_role,
        )
        for block in selector.blocks[:3]
    ]
    return [root, *children]


def _tree_blockers(selector: CortexMemoryRetrievalSelectorRecord | None) -> list[str]:
    if selector is None:
        return ["missing_memory_retrieval_selector"]
    if selector.selector_allowed is not True:
        return ["memory_retrieval_selector_not_allowed"]
    if selector.next_action != "seed_hypothesis_tree":
        return ["selector_not_waiting_hypothesis_tree"]
    if selector.selected_block_count < 1:
        return ["selector_has_no_blocks"]
    return []


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
