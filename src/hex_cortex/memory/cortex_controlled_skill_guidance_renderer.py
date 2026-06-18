from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_controlled_skill_use import (
    CORTEX_CONTROLLED_SKILL_USE_FILENAME,
    CortexControlledSkillUseJsonlStore,
    CortexControlledSkillUseRecord,
)

CORTEX_CONTROLLED_SKILL_GUIDANCE_RENDERER_FILENAME = "cortex-controlled-skill-guidance-renderer.jsonl"
_SAFE_ACTIONS = [
    "Inspect the current memory-first state and list the evidence already present.",
    "Map the selected reusable rule to one small architecture improvement proposal.",
    "Identify required receipts before changing any persistent project state.",
    "Return a reviewable plan with blockers, verification commands, and next_action only.",
]
_BLOCKED_WORDS = {"execute", "deploy", "live", "trade", "order", "buy", "sell", "delete", "destroy"}


class CortexControlledSkillGuidanceRendererRecord(BaseModel):
    guidance_id: str = Field(default_factory=lambda: f"cortex_controlled_skill_guidance_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_use_id: str | None
    source_use_hash: str | None
    selected_skill_key: str | None
    selected_domain: str | None
    selected_reusable_rule: str | None
    intent: str | None
    task_text: str | None
    guidance_status: str
    guidance_decision: str
    guidance_allowed: bool
    guidance_title: str | None
    guidance_steps: list[str]
    forbidden_terms: list[str]
    next_action: str
    blockers: list[str]
    guidance_hash: str
    reasons: list[str]


class CortexControlledSkillGuidanceRendererJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexControlledSkillGuidanceRendererRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexControlledSkillGuidanceRendererRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex controlled skill guidance renderer {line_number}") from exc
        return records

    def save(self, records: list[CortexControlledSkillGuidanceRendererRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_controlled_skill_guidance_renderer(profile: Path) -> dict[str, object]:
    use = _latest_use(profile)
    record = _guidance_record(profile, use)
    path = profile / CORTEX_CONTROLLED_SKILL_GUIDANCE_RENDERER_FILENAME
    store = CortexControlledSkillGuidanceRendererJsonlStore(path)
    current = store.load()
    if record.source_use_hash and any(item.source_use_hash == record.source_use_hash for item in current):
        records: list[CortexControlledSkillGuidanceRendererRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "guidance_type": "cortex_controlled_skill_guidance_renderer",
        "profile_path": str(profile),
        "guidance_path": str(path),
        "guidance_count": count,
        "guidance_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_controlled_skill_guidance_renderers(path: Path) -> dict[str, object]:
    records = CortexControlledSkillGuidanceRendererJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.guidance_allowed]
    return {
        "inspect_type": "cortex_controlled_skill_guidance_renderer",
        "path": str(path),
        "exists": path.exists(),
        "total_guidance_count": len(records),
        "allowed_guidance_count": len(allowed),
        "latest_guidance_id": latest.guidance_id if latest else None,
        "latest_guidance_status": latest.guidance_status if latest else None,
        "latest_guidance_decision": latest.guidance_decision if latest else None,
        "latest_guidance_allowed": latest.guidance_allowed if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_guidance_hash": latest.guidance_hash if latest else None,
    }


def _latest_use(profile: Path) -> CortexControlledSkillUseRecord | None:
    records = CortexControlledSkillUseJsonlStore(profile / CORTEX_CONTROLLED_SKILL_USE_FILENAME).load()
    return records[-1] if records else None


def _guidance_record(profile: Path, use: CortexControlledSkillUseRecord | None) -> CortexControlledSkillGuidanceRendererRecord:
    blockers = _guidance_blockers(use)
    allowed = not blockers
    status = "rendered" if allowed else "blocked"
    decision = "controlled_skill_guidance_rendered" if allowed else "controlled_skill_guidance_blocked"
    next_action = "record_guidance_receipt" if allowed else "repair_controlled_skill_use"
    reasons = ["controlled_skill_use_allowed", "guidance_rendered_from_active_skill"] if allowed else blockers
    steps = _render_steps(use) if allowed and use else []
    title = "Safe HEX-CORTEX memory-first improvement guidance" if allowed else None
    guidance_hash = _hash(
        str(profile),
        use.use_hash if use else "missing_use",
        use.selected_skill_key if use else "missing_skill",
        decision,
        next_action,
        *steps,
        *reasons,
    )
    return CortexControlledSkillGuidanceRendererRecord(
        profile_path=str(profile),
        source_use_id=use.use_id if use else None,
        source_use_hash=use.use_hash if use else None,
        selected_skill_key=use.selected_skill_key if use else None,
        selected_domain=use.selected_domain if use else None,
        selected_reusable_rule=use.selected_reusable_rule if use else None,
        intent=use.intent if use else None,
        task_text=use.task_text if use else None,
        guidance_status=status,
        guidance_decision=decision,
        guidance_allowed=allowed,
        guidance_title=title,
        guidance_steps=steps,
        forbidden_terms=sorted(_BLOCKED_WORDS),
        next_action=next_action,
        blockers=blockers,
        guidance_hash=guidance_hash,
        reasons=reasons,
    )


def _render_steps(use: CortexControlledSkillUseRecord) -> list[str]:
    rule = use.selected_reusable_rule or "No reusable rule selected."
    return [
        f"Apply reusable rule: {rule}",
        *_SAFE_ACTIONS,
        "Stop if the plan requests market, deployment, destructive, or live execution actions.",
    ]


def _guidance_blockers(use: CortexControlledSkillUseRecord | None) -> list[str]:
    blockers = []
    if use is None:
        return ["missing_controlled_skill_use"]
    if use.use_allowed is not True:
        blockers.append("controlled_skill_use_not_allowed")
    if use.next_action != "render_controlled_skill_guidance":
        blockers.append("controlled_skill_use_not_waiting_guidance")
    if not use.selected_skill_key or not use.selected_reusable_rule:
        blockers.append("missing_selected_skill_or_rule")
    words = {part.strip(".,:;!?()[]{}\"'").lower() for part in use.task_text.split()}
    if words & _BLOCKED_WORDS:
        blockers.append("task_contains_blocked_action")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
