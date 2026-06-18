from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_skill_guidance_renderer import (
    CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME,
    CortexSkillGuidanceRendererJsonlStore,
    CortexSkillGuidanceRendererRecord,
)

CORTEX_GUIDED_REASONING_FRAME_FILENAME = "cortex-guided-reasoning-frame.jsonl"


class CortexGuidedReasoningFrameRecord(BaseModel):
    frame_id: str = Field(default_factory=lambda: f"cortex_guided_reasoning_frame_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_guidance_id: str | None
    source_guidance_hash: str | None
    source_use_hash: str | None
    source_index_hash: str | None
    source_apply_hash: str | None
    source_library_hash: str | None
    source_learning_ids: list[str]
    skill_key: str | None
    domain: str | None
    intent: str | None
    question: str
    applicable_rule: str | None
    constraints: list[str]
    recommended_direction: str
    blocked_directions: list[str]
    frame_status: str
    frame_decision: str
    frame_allowed: bool
    next_action: str
    blockers: list[str]
    frame_hash: str
    reasons: list[str]


class CortexGuidedReasoningFrameJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexGuidedReasoningFrameRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexGuidedReasoningFrameRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex guided reasoning frame {line_number}") from exc
        return records

    def save(self, records: list[CortexGuidedReasoningFrameRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_guided_reasoning_frame(profile: Path) -> dict[str, object]:
    guidance = _latest_guidance(profile)
    path = profile / CORTEX_GUIDED_REASONING_FRAME_FILENAME
    store = CortexGuidedReasoningFrameJsonlStore(path)
    current = store.load()
    if guidance and any(record.source_guidance_hash == guidance.guidance_hash for record in current):
        records: list[CortexGuidedReasoningFrameRecord] = []
    else:
        records = [_frame_record(profile, guidance)]
    count = store.save([*current, *records])
    return {
        "frame_type": "cortex_guided_reasoning_frame",
        "profile_path": str(profile),
        "frame_path": str(path),
        "frame_count": count,
        "frame_records": [record.model_dump(mode="json") for record in records],
    }


def summarize_cortex_guided_reasoning_frames(path: Path) -> dict[str, object]:
    records = CortexGuidedReasoningFrameJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.frame_allowed]
    return {
        "inspect_type": "cortex_guided_reasoning_frame",
        "path": str(path),
        "exists": path.exists(),
        "total_frame_count": len(records),
        "allowed_frame_count": len(allowed),
        "latest_frame_id": latest.frame_id if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_intent": latest.intent if latest else None,
        "latest_frame_status": latest.frame_status if latest else None,
        "latest_frame_decision": latest.frame_decision if latest else None,
        "latest_frame_allowed": latest.frame_allowed if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_frame_hash": latest.frame_hash if latest else None,
    }


def _latest_guidance(profile: Path) -> CortexSkillGuidanceRendererRecord | None:
    records = CortexSkillGuidanceRendererJsonlStore(
        profile / CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME
    ).load()
    return records[-1] if records else None


def _frame_record(
    profile: Path,
    guidance: CortexSkillGuidanceRendererRecord | None,
) -> CortexGuidedReasoningFrameRecord:
    blockers = _frame_blockers(guidance)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "guided_reasoning_frame_ready" if allowed else "guided_reasoning_frame_blocked"
    next_action = "choose_next_build_step_with_guidance" if allowed else "repair_skill_guidance"
    reasons = ["guidance_allowed", "reasoning_frame_built"] if allowed else blockers
    question = guidance.task_text if guidance and guidance.task_text else "No valid guidance question available."
    applicable_rule = guidance.reusable_rule if guidance else None
    constraints = guidance.constraints if guidance and allowed else []
    recommended_direction = _recommended_direction(guidance, allowed)
    blocked_directions = _blocked_directions(guidance, allowed)
    frame_hash = _hash(
        str(profile),
        guidance.guidance_hash if guidance else "missing_guidance",
        question,
        applicable_rule or "missing_rule",
        recommended_direction,
        decision,
        next_action,
        *constraints,
        *blocked_directions,
        *reasons,
    )
    return CortexGuidedReasoningFrameRecord(
        profile_path=str(profile),
        source_guidance_id=guidance.guidance_id if guidance else None,
        source_guidance_hash=guidance.guidance_hash if guidance else None,
        source_use_hash=guidance.source_use_hash if guidance else None,
        source_index_hash=guidance.source_index_hash if guidance else None,
        source_apply_hash=guidance.source_apply_hash if guidance else None,
        source_library_hash=guidance.source_library_hash if guidance else None,
        source_learning_ids=guidance.source_learning_ids if guidance else [],
        skill_key=guidance.skill_key if guidance else None,
        domain=guidance.domain if guidance else None,
        intent=guidance.intent if guidance else None,
        question=question,
        applicable_rule=applicable_rule,
        constraints=constraints,
        recommended_direction=recommended_direction,
        blocked_directions=blocked_directions,
        frame_status=status,
        frame_decision=decision,
        frame_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        frame_hash=frame_hash,
        reasons=reasons,
    )


def _frame_blockers(guidance: CortexSkillGuidanceRendererRecord | None) -> list[str]:
    blockers = []
    if guidance is None:
        blockers.append("missing_skill_guidance")
        return blockers
    if guidance.guidance_allowed is not True:
        blockers.append("skill_guidance_not_allowed")
    if guidance.guidance_decision != "skill_guidance_rendered":
        blockers.append("skill_guidance_not_rendered")
    if guidance.next_action != "use_guidance_in_reasoning":
        blockers.append("guidance_not_waiting_reasoning")
    if not guidance.reusable_rule or not guidance.guidance_steps:
        blockers.append("guidance_missing_rule_or_steps")
    if not guidance.source_learning_ids:
        blockers.append("missing_learning_lineage")
    return blockers


def _recommended_direction(guidance: CortexSkillGuidanceRendererRecord | None, allowed: bool) -> str:
    if not allowed or guidance is None:
        return "Repair guidance before using it for reasoning."
    return "Use the active rule to prefer learning, memory, evidence, and alignment improvements before adding routers, executors, or irreversible behavior."


def _blocked_directions(guidance: CortexSkillGuidanceRendererRecord | None, allowed: bool) -> list[str]:
    if not allowed or guidance is None:
        return ["Do not use blocked guidance for build decisions."]
    return [
        "Do not execute or mutate state from the reasoning frame.",
        "Do not add routers or executors before checking whether better learning memory is needed.",
        "Do not detach the recommendation from its source lineage.",
    ]


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
