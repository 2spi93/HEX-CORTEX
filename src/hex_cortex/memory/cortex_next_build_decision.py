from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_guided_reasoning_frame import (
    CORTEX_GUIDED_REASONING_FRAME_FILENAME,
    CortexGuidedReasoningFrameJsonlStore,
    CortexGuidedReasoningFrameRecord,
)

CORTEX_NEXT_BUILD_DECISION_FILENAME = "cortex-next-build-decision.jsonl"

_ALLOWED_DIRECTIONS = {
    "continue_learning_memory",
    "build_retrieval_selector",
    "build_skill_evaluator",
    "hold",
    "repair",
}


class CortexNextBuildDecisionRecord(BaseModel):
    decision_id: str = Field(default_factory=lambda: f"cortex_next_build_decision_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_frame_id: str | None
    source_frame_hash: str | None
    source_guidance_hash: str | None
    source_use_hash: str | None
    source_learning_ids: list[str]
    skill_key: str | None
    domain: str | None
    question: str | None
    applicable_rule: str | None
    chosen_build_direction: str
    recommended_direction: str
    blocked_build_directions: list[str]
    decision_status: str
    decision_result: str
    decision_allowed: bool
    next_action: str
    blockers: list[str]
    decision_hash: str
    reasons: list[str]


class CortexNextBuildDecisionJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexNextBuildDecisionRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexNextBuildDecisionRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex next build decision {line_number}") from exc
        return records

    def save(self, records: list[CortexNextBuildDecisionRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_next_build_decision(profile: Path) -> dict[str, object]:
    frame = _latest_frame(profile)
    path = profile / CORTEX_NEXT_BUILD_DECISION_FILENAME
    store = CortexNextBuildDecisionJsonlStore(path)
    current = store.load()
    if frame and any(record.source_frame_hash == frame.frame_hash for record in current):
        records: list[CortexNextBuildDecisionRecord] = []
    else:
        records = [_decision_record(profile, frame)]
    count = store.save([*current, *records])
    return {
        "decision_type": "cortex_next_build_decision",
        "profile_path": str(profile),
        "decision_path": str(path),
        "decision_count": count,
        "decision_records": [record.model_dump(mode="json") for record in records],
    }


def summarize_cortex_next_build_decisions(path: Path) -> dict[str, object]:
    records = CortexNextBuildDecisionJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.decision_allowed]
    return {
        "inspect_type": "cortex_next_build_decision",
        "path": str(path),
        "exists": path.exists(),
        "total_decision_count": len(records),
        "allowed_decision_count": len(allowed),
        "latest_decision_id": latest.decision_id if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_chosen_build_direction": latest.chosen_build_direction if latest else None,
        "latest_decision_status": latest.decision_status if latest else None,
        "latest_decision_result": latest.decision_result if latest else None,
        "latest_decision_allowed": latest.decision_allowed if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_decision_hash": latest.decision_hash if latest else None,
    }


def _latest_frame(profile: Path) -> CortexGuidedReasoningFrameRecord | None:
    records = CortexGuidedReasoningFrameJsonlStore(
        profile / CORTEX_GUIDED_REASONING_FRAME_FILENAME
    ).load()
    return records[-1] if records else None


def _decision_record(
    profile: Path,
    frame: CortexGuidedReasoningFrameRecord | None,
) -> CortexNextBuildDecisionRecord:
    blockers = _decision_blockers(frame)
    allowed = not blockers
    chosen = _choose_direction(frame, allowed)
    next_action = _next_action(chosen, allowed)
    status = "ready" if allowed else "blocked"
    result = "next_build_decision_ready" if allowed else "next_build_decision_blocked"
    reasons = ["guided_reasoning_frame_ready", f"chosen_{chosen}"] if allowed else blockers
    blocked_directions = _blocked_directions(frame, allowed)
    decision_hash = _hash(
        str(profile),
        frame.frame_hash if frame else "missing_frame",
        chosen,
        next_action,
        result,
        *blocked_directions,
        *reasons,
    )
    return CortexNextBuildDecisionRecord(
        profile_path=str(profile),
        source_frame_id=frame.frame_id if frame else None,
        source_frame_hash=frame.frame_hash if frame else None,
        source_guidance_hash=frame.source_guidance_hash if frame else None,
        source_use_hash=frame.source_use_hash if frame else None,
        source_learning_ids=frame.source_learning_ids if frame else [],
        skill_key=frame.skill_key if frame else None,
        domain=frame.domain if frame else None,
        question=frame.question if frame else None,
        applicable_rule=frame.applicable_rule if frame else None,
        chosen_build_direction=chosen,
        recommended_direction=frame.recommended_direction if frame else "Repair frame before deciding.",
        blocked_build_directions=blocked_directions,
        decision_status=status,
        decision_result=result,
        decision_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        decision_hash=decision_hash,
        reasons=reasons,
    )


def _decision_blockers(frame: CortexGuidedReasoningFrameRecord | None) -> list[str]:
    blockers = []
    if frame is None:
        blockers.append("missing_guided_reasoning_frame")
        return blockers
    if frame.frame_allowed is not True:
        blockers.append("guided_reasoning_frame_not_allowed")
    if frame.frame_decision != "guided_reasoning_frame_ready":
        blockers.append("guided_reasoning_frame_not_ready")
    if frame.next_action != "choose_next_build_step_with_guidance":
        blockers.append("frame_not_waiting_next_build_decision")
    if not frame.applicable_rule or not frame.source_learning_ids:
        blockers.append("missing_rule_or_learning_lineage")
    return blockers


def _choose_direction(frame: CortexGuidedReasoningFrameRecord | None, allowed: bool) -> str:
    if not allowed or frame is None:
        return "repair"
    text = " ".join([frame.recommended_direction, frame.applicable_rule or ""]).lower()
    if "learning" in text or "memory" in text:
        return "continue_learning_memory"
    if "retrieval" in text:
        return "build_retrieval_selector"
    if "evaluator" in text or "evaluation" in text:
        return "build_skill_evaluator"
    return "hold"


def _next_action(chosen: str, allowed: bool) -> str:
    if not allowed:
        return "repair_guided_reasoning_frame"
    actions = {
        "continue_learning_memory": "build_memory_retrieval_selector",
        "build_retrieval_selector": "build_memory_retrieval_selector",
        "build_skill_evaluator": "build_skill_evaluator",
        "hold": "hold_next_build_decision",
        "repair": "repair_guided_reasoning_frame",
    }
    return actions[chosen]


def _blocked_directions(frame: CortexGuidedReasoningFrameRecord | None, allowed: bool) -> list[str]:
    if not allowed or frame is None:
        return ["Do not choose a build direction from a blocked frame."]
    blocked = list(frame.blocked_directions)
    blocked.append("Do not add execution, mutation, or router behavior before the next learning/memory selector exists.")
    return blocked


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
