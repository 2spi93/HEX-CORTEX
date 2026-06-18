from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_guided_reasoning_frame import (
    CORTEX_GUIDED_REASONING_FRAME_FILENAME,
    CortexGuidedReasoningFrameJsonlStore,
)
from hex_cortex.memory.cortex_learning_event import (
    CORTEX_LEARNING_EVENT_FILENAME,
    CortexLearningEventJsonlStore,
)
from hex_cortex.memory.cortex_next_build_decision import (
    CORTEX_NEXT_BUILD_DECISION_FILENAME,
    CortexNextBuildDecisionJsonlStore,
)

CORTEX_MEMORY_RETRIEVAL_SELECTOR_FILENAME = "cortex-memory-retrieval-selector.jsonl"


class CortexMemoryRetrievalBlock(BaseModel):
    block_id: str
    block_type: str
    source_ref: str
    summary: str
    priority: int = Field(ge=0)
    latent_role: str
    dynamics_role: str
    future_role: str
    cost_role: str
    lineage_hashes: list[str]


class CortexMemoryRetrievalSelectorRecord(BaseModel):
    selector_id: str = Field(default_factory=lambda: f"cortex_memory_retrieval_selector_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_decision_id: str | None
    source_decision_hash: str | None
    selector_status: str
    selector_decision: str
    selector_allowed: bool
    selected_block_count: int = Field(ge=0)
    selected_block_ids: list[str]
    blocks: list[CortexMemoryRetrievalBlock]
    world_model_alignment: list[str]
    next_action: str
    blockers: list[str]
    selector_hash: str
    reasons: list[str]


class CortexMemoryRetrievalSelectorJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexMemoryRetrievalSelectorRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexMemoryRetrievalSelectorRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex memory retrieval selector {line_number}") from exc
        return records

    def save(self, records: list[CortexMemoryRetrievalSelectorRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_memory_retrieval_selector(profile: Path) -> dict[str, object]:
    record = _selector_record(profile)
    path = profile / CORTEX_MEMORY_RETRIEVAL_SELECTOR_FILENAME
    store = CortexMemoryRetrievalSelectorJsonlStore(path)
    current = store.load()
    if record.source_decision_hash and any(item.source_decision_hash == record.source_decision_hash for item in current):
        records: list[CortexMemoryRetrievalSelectorRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "selector_type": "cortex_memory_retrieval_selector",
        "profile_path": str(profile),
        "selector_path": str(path),
        "selector_count": count,
        "selector_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_memory_retrieval_selectors(path: Path) -> dict[str, object]:
    records = CortexMemoryRetrievalSelectorJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.selector_allowed]
    return {
        "inspect_type": "cortex_memory_retrieval_selector",
        "path": str(path),
        "exists": path.exists(),
        "total_selector_count": len(records),
        "allowed_selector_count": len(allowed),
        "latest_selector_id": latest.selector_id if latest else None,
        "latest_selector_status": latest.selector_status if latest else None,
        "latest_selector_decision": latest.selector_decision if latest else None,
        "latest_selector_allowed": latest.selector_allowed if latest else None,
        "latest_selected_block_count": latest.selected_block_count if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_selector_hash": latest.selector_hash if latest else None,
    }


def _selector_record(profile: Path) -> CortexMemoryRetrievalSelectorRecord:
    decision = _latest(profile, CORTEX_NEXT_BUILD_DECISION_FILENAME, CortexNextBuildDecisionJsonlStore)
    frame = _latest(profile, CORTEX_GUIDED_REASONING_FRAME_FILENAME, CortexGuidedReasoningFrameJsonlStore)
    learning_records = CortexLearningEventJsonlStore(profile / CORTEX_LEARNING_EVENT_FILENAME).load()
    blockers = _selector_blockers(decision, frame)
    blocks = [] if blockers else _blocks(decision, frame, learning_records)
    allowed = not blockers and bool(blocks)
    status = "ready" if allowed else "blocked"
    selector_decision = "memory_retrieval_selector_ready" if allowed else "memory_retrieval_selector_blocked"
    next_action = "seed_hypothesis_tree" if allowed else "repair_memory_retrieval_selector"
    reasons = ["semantic_blocks_selected", "world_model_roles_attached"] if allowed else blockers
    selector_hash = _hash(
        str(profile),
        decision.decision_hash if decision else "missing_decision",
        *[block.block_id for block in blocks],
        selector_decision,
        next_action,
        *reasons,
    )
    return CortexMemoryRetrievalSelectorRecord(
        profile_path=str(profile),
        source_decision_id=decision.decision_id if decision else None,
        source_decision_hash=decision.decision_hash if decision else None,
        selector_status=status,
        selector_decision=selector_decision,
        selector_allowed=allowed,
        selected_block_count=len(blocks),
        selected_block_ids=[block.block_id for block in blocks],
        blocks=blocks,
        world_model_alignment=["latent_state", "dynamics", "future_prediction", "cost_evaluation"],
        next_action=next_action,
        blockers=blockers if blockers else ([] if blocks else ["no_blocks_selected"]),
        selector_hash=selector_hash,
        reasons=reasons,
    )


def _blocks(decision, frame, learning_records) -> list[CortexMemoryRetrievalBlock]:
    blocks = [
        CortexMemoryRetrievalBlock(
            block_id="state:build_choice",
            block_type="state",
            source_ref=decision.decision_id,
            summary=f"{decision.chosen_build_direction} -> {decision.next_action}",
            priority=100,
            latent_role="current abstract state",
            dynamics_role="transition from frame to build choice",
            future_role="next memory step",
            cost_role="prefer small verified steps",
            lineage_hashes=[decision.decision_hash, decision.source_frame_hash or "missing_frame"],
        ),
        CortexMemoryRetrievalBlock(
            block_id="rule:active_frame",
            block_type="rule",
            source_ref=frame.frame_id,
            summary=frame.applicable_rule or "missing rule",
            priority=95,
            latent_role="compressed reusable rule",
            dynamics_role="shapes the next branch",
            future_role="keeps memory-first trajectory",
            cost_role="limits context and drift",
            lineage_hashes=[frame.frame_hash, frame.source_guidance_hash or "missing_guidance"],
        ),
    ]
    for item in learning_records[-3:]:
        blocks.append(
            CortexMemoryRetrievalBlock(
                block_id=f"learning:{item.learning_id}",
                block_type="learning",
                source_ref=item.learning_id,
                summary=item.reusable_rule,
                priority=70,
                latent_role="experience-derived rule",
                dynamics_role="feedback update",
                future_role="anticipates mission drift",
                cost_role="reduces repeated error",
                lineage_hashes=[item.learning_hash],
            )
        )
    return sorted(blocks, key=lambda block: block.priority, reverse=True)[:6]


def _selector_blockers(decision, frame) -> list[str]:
    blockers = []
    if decision is None:
        blockers.append("missing_next_build_decision")
        return blockers
    if decision.decision_allowed is not True:
        blockers.append("next_build_decision_not_allowed")
    if decision.next_action != "build_memory_retrieval_selector":
        blockers.append("decision_not_waiting_memory_retrieval_selector")
    if frame is None:
        blockers.append("missing_guided_reasoning_frame")
    elif frame.frame_allowed is not True:
        blockers.append("guided_reasoning_frame_not_allowed")
    return blockers


def _latest(profile: Path, filename: str, store_cls):
    records = store_cls(profile / filename).load()
    return records[-1] if records else None


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
