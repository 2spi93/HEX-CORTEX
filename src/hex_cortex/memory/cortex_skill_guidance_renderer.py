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

CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME = "cortex-skill-guidance-renderer.jsonl"


class CortexSkillGuidanceRendererRecord(BaseModel):
    guidance_id: str = Field(default_factory=lambda: f"cortex_skill_guidance_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_use_id: str | None
    source_use_hash: str | None
    source_index_hash: str | None
    source_apply_hash: str | None
    source_library_hash: str | None
    source_learning_ids: list[str]
    skill_key: str | None
    domain: str | None
    intent: str | None
    task_text: str | None
    reusable_rule: str | None
    guidance_status: str
    guidance_decision: str
    guidance_allowed: bool
    guidance_title: str
    guidance_steps: list[str]
    constraints: list[str]
    next_action: str
    blockers: list[str]
    guidance_hash: str
    reasons: list[str]


class CortexSkillGuidanceRendererJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexSkillGuidanceRendererRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexSkillGuidanceRendererRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex skill guidance renderer {line_number}") from exc
        return records

    def save(self, records: list[CortexSkillGuidanceRendererRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def render_cortex_skill_guidance(profile: Path) -> dict[str, object]:
    use = _latest_use(profile)
    path = profile / CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME
    store = CortexSkillGuidanceRendererJsonlStore(path)
    current = store.load()
    if use and any(record.source_use_hash == use.use_hash for record in current):
        records: list[CortexSkillGuidanceRendererRecord] = []
    else:
        records = [_guidance_record(profile, use)]
    count = store.save([*current, *records])
    return {
        "guidance_type": "cortex_skill_guidance_renderer",
        "profile_path": str(profile),
        "guidance_path": str(path),
        "guidance_count": count,
        "guidance_records": [record.model_dump(mode="json") for record in records],
    }


def summarize_cortex_skill_guidance_renderers(path: Path) -> dict[str, object]:
    records = CortexSkillGuidanceRendererJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.guidance_allowed]
    return {
        "inspect_type": "cortex_skill_guidance_renderer",
        "path": str(path),
        "exists": path.exists(),
        "total_guidance_count": len(records),
        "allowed_guidance_count": len(allowed),
        "latest_guidance_id": latest.guidance_id if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_intent": latest.intent if latest else None,
        "latest_guidance_status": latest.guidance_status if latest else None,
        "latest_guidance_decision": latest.guidance_decision if latest else None,
        "latest_guidance_allowed": latest.guidance_allowed if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_guidance_hash": latest.guidance_hash if latest else None,
    }


def _latest_use(profile: Path) -> CortexControlledSkillUseRecord | None:
    records = CortexControlledSkillUseJsonlStore(
        profile / CORTEX_CONTROLLED_SKILL_USE_FILENAME
    ).load()
    return records[-1] if records else None


def _guidance_record(
    profile: Path,
    use: CortexControlledSkillUseRecord | None,
) -> CortexSkillGuidanceRendererRecord:
    blockers = _guidance_blockers(use)
    allowed = not blockers
    status = "rendered" if allowed else "blocked"
    decision = "skill_guidance_rendered" if allowed else "skill_guidance_blocked"
    next_action = "use_guidance_in_reasoning" if allowed else "revise_controlled_skill_use"
    reasons = ["controlled_skill_use_allowed", "guidance_rendered_from_reusable_rule"] if allowed else blockers
    title = _title(use, allowed)
    steps = _steps(use) if allowed and use else []
    constraints = _constraints(use) if allowed and use else []
    guidance_hash = _hash(
        str(profile),
        use.use_hash if use else "missing_use",
        use.selected_skill_key if use and use.selected_skill_key else "missing_skill",
        use.selected_reusable_rule if use and use.selected_reusable_rule else "missing_rule",
        decision,
        next_action,
        *reasons,
        *steps,
        *constraints,
    )
    return CortexSkillGuidanceRendererRecord(
        profile_path=str(profile),
        source_use_id=use.use_id if use else None,
        source_use_hash=use.use_hash if use else None,
        source_index_hash=use.source_index_hash if use else None,
        source_apply_hash=use.source_apply_hash if use else None,
        source_library_hash=use.source_library_hash if use else None,
        source_learning_ids=use.source_learning_ids if use else [],
        skill_key=use.selected_skill_key if use else None,
        domain=use.selected_domain if use else None,
        intent=use.intent if use else None,
        task_text=use.task_text if use else None,
        reusable_rule=use.selected_reusable_rule if use else None,
        guidance_status=status,
        guidance_decision=decision,
        guidance_allowed=allowed,
        guidance_title=title,
        guidance_steps=steps,
        constraints=constraints,
        next_action=next_action,
        blockers=blockers,
        guidance_hash=guidance_hash,
        reasons=reasons,
    )


def _guidance_blockers(use: CortexControlledSkillUseRecord | None) -> list[str]:
    blockers = []
    if use is None:
        blockers.append("missing_controlled_skill_use")
        return blockers
    if use.use_allowed is not True:
        blockers.append("controlled_skill_use_not_allowed")
    if use.use_decision != "controlled_skill_use_allowed":
        blockers.append("controlled_skill_use_decision_not_allowed")
    if use.next_action != "render_controlled_skill_guidance":
        blockers.append("controlled_skill_use_not_waiting_guidance")
    if not use.selected_skill_key or not use.selected_reusable_rule:
        blockers.append("missing_selected_skill_or_rule")
    if not use.source_learning_ids:
        blockers.append("missing_learning_lineage")
    return blockers


def _title(use: CortexControlledSkillUseRecord | None, allowed: bool) -> str:
    if not allowed or use is None:
        return "Skill guidance blocked"
    return f"Guidance for {use.selected_skill_key}"


def _steps(use: CortexControlledSkillUseRecord) -> list[str]:
    return [
        f"Read the current task: {use.task_text}",
        f"Apply the reusable rule: {use.selected_reusable_rule}",
        "Prefer learning/memory improvements before adding routers, executors, or irreversible actions.",
        "Produce reasoning guidance only; do not execute changes from this renderer.",
    ]


def _constraints(use: CortexControlledSkillUseRecord) -> list[str]:
    return [
        f"Intent must remain controlled: {use.intent}",
        "No destructive action is authorized by this guidance.",
        "Keep lineage attached to the selected active skill.",
        "Escalate to a separate gate before any execution, mutation, or external side effect.",
    ]


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
